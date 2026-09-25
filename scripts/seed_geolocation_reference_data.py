#!/usr/bin/env python3
"""
Seed the CONTINENT -> REGION reference hierarchy of the BookAnything backend
(tb_geo_location) from platform/data/geolocation/continents-regions-un-m49.json.

Country imports (NiFi step 8) need the parent REGION to exist: without it every
POST /country fails. This script is idempotent and never deletes anything:
  - missing continents/regions are created;
  - existing ones (matched by friendlyId) get their name and additionalDetailsMap
    (m49Code, memberCountriesIso3, ...) updated when they differ; other detail
    keys (e.g. AI enrichment) are kept;
  - existing countries whose parent region disagrees with the reference data are
    reported. The backend PUT ignores parentId, so they are not moved; the report
    prints the SQL to fix them.

Talks to the backend Service through a kubectl port-forward (in-cluster API, the
same one NiFi uses).

Usage:
  scripts/seed_geolocation_reference_data.py            # apply
  scripts/seed_geolocation_reference_data.py --dry-run  # show what would change
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

NAMESPACE = "drr-tnt-swfabrik-europe-dev"
SERVICE = "svc/bookanything-monolith-backend-01"
REMOTE_PORT = 8060
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                         "platform", "data", "geolocation", "continents-regions-un-m49.json")
SOURCE = "UN-M49"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    def __init__(self, base):
        self.base = base

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode()
                return json.loads(text) if text else None
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {e.read().decode()[:300]}") from None

    def list_all(self, type_):
        out, page = [], 0
        while True:
            res = self.call("GET", f"/api/v1/geolocations/{type_}?size=500&page={page}")
            out += res["content"]
            page += 1
            if page >= res["page"]["totalPages"]:
                return out


def desired_details(entry, extra):
    return {"source": SOURCE, "referenceData": True, "m49Code": entry["m49Code"], **extra}


def reconcile(api, type_, entry, parent_id, existing, extra, dry_run, stats):
    """Create or update one continent/region. Returns its id (None on dry-run create)."""
    fid = entry["friendlyId"]
    want = desired_details(entry, extra)
    cur = existing.get(fid)
    if cur is None:
        print(f"  + create {type_} {fid} '{entry['name']}'")
        stats["created"] += 1
        if dry_run:
            return None
        body = {"name": entry["name"], "alias": fid, "friendlyId": fid,
                "additionalDetailsMap": want, "parentId": parent_id}
        return api.call("POST", f"/api/v1/geolocations/{type_}", body)["id"]

    if parent_id is not None and cur.get("parentId") != parent_id:
        print(f"  ! {type_} {fid} (id {cur['id']}) has parentId {cur.get('parentId')}, expected {parent_id}: "
              f"PUT cannot change it, fix manually")
        stats["warnings"] += 1
    details = dict(cur.get("additionalDetailsMap") or {})
    merged = {**details, **want}
    if cur["name"] == entry["name"] and merged == details:
        stats["unchanged"] += 1
        return cur["id"]
    changes = []
    if cur["name"] != entry["name"]:
        changes.append(f"name '{cur['name']}' -> '{entry['name']}'")
    changed_keys = sorted(k for k in want if details.get(k) != want[k])
    if changed_keys:
        changes.append("details " + ", ".join(changed_keys))
    print(f"  ~ update {type_} {fid} (id {cur['id']}): {'; '.join(changes)}")
    stats["updated"] += 1
    if not dry_run:
        body = {"name": entry["name"], "alias": cur.get("alias") or fid, "friendlyId": fid,
                "additionalDetailsMap": merged, "parentId": cur.get("parentId")}
        api.call("PUT", f"/api/v1/geolocations/{type_}/{cur['id']}", body)
    return cur["id"]


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    port = free_port()
    pf = subprocess.Popen(["kubectl", "-n", NAMESPACE, "port-forward", SERVICE, f"{port}:{REMOTE_PORT}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        api = Api(f"http://127.0.0.1:{port}")
        for _ in range(30):
            try:
                api.call("GET", "/api/v1/geolocations/continent?size=1")
                break
            except (OSError, RuntimeError):
                time.sleep(1)
        else:
            sys.exit("ERROR: backend not reachable through port-forward")

        stats = {"created": 0, "updated": 0, "unchanged": 0, "warnings": 0}
        continents = {c["friendlyId"]: c for c in api.list_all("continent")}
        regions = {r["friendlyId"]: r for r in api.list_all("region")}
        region_of_country = {}

        print(f"==> Reconciling reference data{' (dry run)' if dry_run else ''} from {os.path.relpath(DATA_FILE)}")
        for cont in data["continents"]:
            cont_id = reconcile(api, "continent", cont, None, continents, {}, dry_run, stats)
            for reg in cont["regions"]:
                extra = {"continentFriendlyId": cont["friendlyId"], "memberCountriesIso3": reg["countries"]}
                reconcile(api, "region", reg, cont_id, regions, extra, dry_run, stats)
                for iso3 in reg["countries"]:
                    region_of_country[iso3] = reg["friendlyId"]

        # Countries already imported under a wrong region (e.g. USA under SAM on 2026-09-25).
        regions = {r["friendlyId"]: r for r in api.list_all("region")} if not dry_run else regions
        region_by_id = {r["id"]: r["friendlyId"] for r in regions.values()}
        for country in api.list_all("country"):
            want = region_of_country.get(country["friendlyId"])
            have = region_by_id.get(country.get("parentId"))
            if want and have != want and want in regions:
                print(f"  ! country {country['friendlyId']} (id {country['id']}) is under region {have}, "
                      f"expected {want}. Fix (tenant-postgres, DB DBBookAnythingPlatform): "
                      f"UPDATE tb_geo_location SET parent_id = {regions[want]['id']} WHERE id = {country['id']};")
                stats["warnings"] += 1

        print("==> done: " + ", ".join(f"{k}={v}" for k, v in stats.items()))
    finally:
        pf.terminate()
        pf.wait()


if __name__ == "__main__":
    main()
