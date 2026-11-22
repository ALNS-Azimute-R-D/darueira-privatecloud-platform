#!/usr/bin/env python3
"""
generate_opensearch_saved_objects.py
Generates the complete declarative Saved Objects bundle (Index Patterns, Saved Searches,
Visualizations, and Dashboards) for OpenSearch Dashboards in Darueira Private Cloud.
"""

import json
import os

INDEX_PATTERN_ID = "darueira-k8s-logs"
INDEX_PATTERN_TITLE = "darueira-k8s-logs-*"

def make_index_pattern():
    return {
        "id": INDEX_PATTERN_ID,
        "type": "index-pattern",
        "migrationVersion": {"index-pattern": "7.6.0"},
        "references": [],
        "attributes": {
            "title": INDEX_PATTERN_TITLE,
            "timeFieldName": "@timestamp"
        }
    }

def make_search(search_id, title, description, query_str, sort_field="@timestamp", sort_order="desc", columns=None):
    if columns is None:
        columns = ["kubernetes.namespace_name", "kubernetes.pod_name", "stream", "log"]
    return {
        "id": search_id,
        "type": "search",
        "migrationVersion": {"search": "7.9.3"},
        "references": [
            {
                "id": INDEX_PATTERN_ID,
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern"
            }
        ],
        "attributes": {
            "title": title,
            "description": description,
            "columns": columns,
            "sort": [[sort_field, sort_order]],
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": query_str, "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        }
    }

def make_vis_histogram(vis_id, title, query_str, group_field=None, interval="auto"):
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2",
            "enabled": True,
            "type": "date_histogram",
            "schema": "segment",
            "params": {
                "field": "@timestamp",
                "interval": interval,
                "customInterval": "2h",
                "min_doc_count": 1,
                "extended_bounds": {}
            }
        }
    ]
    if group_field:
        aggs.append({
            "id": "3",
            "enabled": True,
            "type": "terms",
            "schema": "group",
            "params": {
                "field": group_field,
                "size": 10,
                "order": "desc",
                "orderBy": "1",
                "otherBucket": True,
                "otherBucketLabel": "Other",
                "missingBucket": False,
                "missingBucketLabel": "Missing"
            }
        })
    
    vis_state = {
        "title": title,
        "type": "histogram",
        "params": {
            "type": "histogram",
            "grid": {"categoryLines": False},
            "categoryAxes": [
                {
                    "id": "CategoryAxis-1",
                    "type": "category",
                    "position": "bottom",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear"},
                    "labels": {"show": True, "truncate": 100},
                    "title": {}
                }
            ],
            "valueAxes": [
                {
                    "id": "ValueAxis-1",
                    "name": "LeftAxis-1",
                    "type": "value",
                    "position": "left",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear", "mode": "normal"},
                    "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                    "title": {"text": "Count"}
                }
            ],
            "seriesParams": [
                {
                    "show": True,
                    "type": "histogram",
                    "mode": "stacked" if group_field else "normal",
                    "data": {"label": "Count", "id": "1"},
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "showCircles": True
                }
            ],
            "addTooltip": True,
            "addLegend": bool(group_field),
            "legendPosition": "right",
            "times": [],
            "addTimeMarker": False
        },
        "aggs": aggs
    }

    return {
        "id": vis_id,
        "type": "visualization",
        "migrationVersion": {"visualization": "7.10.0"},
        "references": [
            {
                "id": INDEX_PATTERN_ID,
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern"
            }
        ],
        "attributes": {
            "title": title,
            "description": "",
            "uiStateJSON": "{}",
            "visState": json.dumps(vis_state),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": query_str, "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        }
    }

def make_vis_pie(vis_id, title, query_str, field, size=10, is_donut=True):
    vis_state = {
        "title": title,
        "type": "pie",
        "params": {
            "type": "pie",
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "isDonut": is_donut,
            "labels": {"show": True, "values": True, "truncate": 100}
        },
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "segment",
                "params": {
                    "field": field,
                    "size": size,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": True,
                    "otherBucketLabel": "Other",
                    "missingBucket": False,
                    "missingBucketLabel": "Missing"
                }
            }
        ]
    }
    return {
        "id": vis_id,
        "type": "visualization",
        "migrationVersion": {"visualization": "7.10.0"},
        "references": [
            {
                "id": INDEX_PATTERN_ID,
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern"
            }
        ],
        "attributes": {
            "title": title,
            "description": "",
            "uiStateJSON": "{}",
            "visState": json.dumps(vis_state),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": query_str, "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        }
    }

def make_vis_horizontal_bar(vis_id, title, query_str, field, size=15):
    vis_state = {
        "title": title,
        "type": "horizontal_bar",
        "params": {
            "type": "horizontal_bar",
            "grid": {"categoryLines": False},
            "categoryAxes": [
                {
                    "id": "CategoryAxis-1",
                    "type": "category",
                    "position": "left",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear"},
                    "labels": {"show": True, "truncate": 100},
                    "title": {}
                }
            ],
            "valueAxes": [
                {
                    "id": "ValueAxis-1",
                    "name": "BottomAxis-1",
                    "type": "value",
                    "position": "bottom",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear", "mode": "normal"},
                    "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                    "title": {"text": "Log Count"}
                }
            ],
            "seriesParams": [
                {
                    "show": True,
                    "type": "horizontal_bar",
                    "mode": "normal",
                    "data": {"label": "Log Count", "id": "1"},
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "showCircles": True
                }
            ],
            "addTooltip": True,
            "addLegend": False,
            "legendPosition": "right",
            "times": [],
            "addTimeMarker": False
        },
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "segment",
                "params": {
                    "field": field,
                    "size": size,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": False,
                    "otherBucketLabel": "Other",
                    "missingBucket": False,
                    "missingBucketLabel": "Missing"
                }
            }
        ]
    }
    return {
        "id": vis_id,
        "type": "visualization",
        "migrationVersion": {"visualization": "7.10.0"},
        "references": [
            {
                "id": INDEX_PATTERN_ID,
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern"
            }
        ],
        "attributes": {
            "title": title,
            "description": "",
            "uiStateJSON": "{}",
            "visState": json.dumps(vis_state),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": query_str, "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        }
    }

def make_vis_metric(vis_id, title, query_str, custom_label="Total Events"):
    vis_state = {
        "title": title,
        "type": "metric",
        "params": {
            "addTooltip": True,
            "addLegend": False,
            "type": "metric",
            "metric": {
                "percentageMode": False,
                "useRanges": False,
                "colorSchema": "Green to Red",
                "metricColorMode": "None",
                "colorsRange": [{"from": 0, "to": 10000}],
                "labels": {"show": True},
                "invertColors": False,
                "style": {
                    "bgFill": "#000",
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": 60
                }
            }
        },
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "count",
                "schema": "metric",
                "params": {"customLabel": custom_label}
            }
        ]
    }
    return {
        "id": vis_id,
        "type": "visualization",
        "migrationVersion": {"visualization": "7.10.0"},
        "references": [
            {
                "id": INDEX_PATTERN_ID,
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern"
            }
        ],
        "attributes": {
            "title": title,
            "description": "",
            "uiStateJSON": "{}",
            "visState": json.dumps(vis_state),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": query_str, "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        }
    }

def make_dashboard(dash_id, title, description, panels, query_str=""):
    """
    panels is a list of tuples: (panel_id, obj_type, obj_id, grid_x, grid_y, grid_w, grid_h)
    """
    panels_json = []
    references = []

    for panel_id, obj_type, obj_id, gx, gy, gw, gh in panels:
        ref_name = f"panel_{panel_id}"
        panel_def = {
            "version": "7.10.0",
            "gridData": {
                "x": gx,
                "y": gy,
                "w": gw,
                "h": gh,
                "i": str(panel_id)
            },
            "panelIndex": str(panel_id),
            "embeddableConfig": {},
            "panelRefName": ref_name
        }
        panels_json.append(panel_def)
        references.append({
            "name": ref_name,
            "type": obj_type,
            "id": obj_id
        })

    return {
        "id": dash_id,
        "type": "dashboard",
        "migrationVersion": {"dashboard": "7.9.3"},
        "references": references,
        "attributes": {
            "title": title,
            "description": description,
            "hits": 0,
            "panelsJSON": json.dumps(panels_json),
            "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
            "version": 1,
            "timeRestore": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": query_str, "language": "kuery"},
                    "filter": []
                })
            }
        }
    }

# Exact (keyword) fields. The analysed text fields split `drr-corpshared-plat` at the hyphens, so a wildcard such as
# `kubernetes.namespace_name: drr-tnt-*` matched almost every document and "Platform", "Tenants" and "ACME" showed the
# same logs. Always query the `.keyword` sub-fields for namespaces and pods.
NS = "kubernetes.namespace_name.keyword"
POD = "kubernetes.pod_name.keyword"
# "Error" means the application said so. The old definition also counted every WARN, every `fail*` and the whole stderr
# stream (Java apps log INFO to stderr), which made 18% of all logs look like errors.
ERR = "log: (ERROR OR Exception OR FATAL OR panic)"

TENANT_NAMESPACES = [
    # (key, label, namespace)
    ("europe", "swfabrik-europe", "drr-tnt-swfabrik-europe-dev"),
    ("latam", "swfabrik-latam", "drr-tnt-swfabrik-latam-dev"),
]

def scope_objects(key, label, scope_q, group_field, search_title, search_desc, all_q=None):
    """The six visualisations (+ the saved search) every scoped dashboard is made of."""
    err_q = scope_q if key == "errors" else f"({scope_q}) AND {ERR}"
    objs = [
        make_vis_metric(f"vis-{key}-total-logs", f"Total {label} Logs", all_q or scope_q, f"{label} Logs"),
        make_vis_metric(f"vis-{key}-total-errors", f"Total {label} Errors", err_q, f"{label} Errors"),
        make_vis_histogram(f"vis-{key}-log-timeline", f"{label} Log Volume (Timeline)", scope_q, group_field),
        make_vis_pie(f"vis-{key}-share", f"{label} Breakdown", scope_q, group_field),
        make_vis_horizontal_bar(f"vis-{key}-top-pods", f"Top {label} Pods by Log Volume", scope_q, POD, 15),
        make_vis_histogram(f"vis-{key}-errors-timeline", f"{label} Errors Timeline", err_q, POD),
    ]
    objs.append(make_search(f"search-{key}-logs", search_title, search_desc, scope_q))
    return objs


def scope_dashboard(key, dash_id, title, description, scope_q):
    panels = [
        (1, "visualization", f"vis-{key}-total-logs", 0, 0, 12, 6),
        (2, "visualization", f"vis-{key}-total-errors", 12, 0, 12, 6),
        (3, "visualization", f"vis-{key}-log-timeline", 0, 6, 24, 12),
        (4, "visualization", f"vis-{key}-share", 0, 18, 12, 12),
        (5, "visualization", f"vis-{key}-top-pods", 12, 18, 12, 12),
        (6, "visualization", f"vis-{key}-errors-timeline", 0, 30, 24, 12),
        (7, "search", f"search-{key}-logs", 0, 42, 24, 16),
    ]
    return make_dashboard(dash_id, title, description, panels, scope_q)


def generate_bundle():
    objects = [make_index_pattern()]

    # Scopes: (key, dashboard id, title, description, query, group field, search title, search description)
    scopes = [
        ("platform", "dashboard-platform-overview", "🏢 Darueira Platform - Enterprise Control Plane Overview",
         "All Corporate Shared Services (drr-corpshared-*: plat, mgmt, secr, obs)",
         f"{NS}: drr-corpshared-*", NS,
         "🏢 [Platform] Enterprise Shared Services Logs", "Logs from the drr-corpshared-* namespaces"),
        ("tenants", "dashboard-tenants-overview", "👥 Darueira Tenants - Multi-Tenant Workloads Overview",
         "Log activity across every tenant namespace (drr-tnt-*)",
         f"{NS}: drr-tnt-*", NS,
         "👥 [Tenants] All Multi-Tenant Workload Logs", "Logs from every tenant environment (drr-tnt-*)"),
    ]
    for key, label, ns in TENANT_NAMESPACES:
        scopes.append((
            key, f"dashboard-tenant-{key}-deepdive", f"🎯 Tenant Deep-Dive - {label} ({ns})",
            f"Workloads of tenant {label}: business apps, tenant-postgres, tenant-minio, tenant-keycloak, tenant-openbao",
            f"{NS}: {ns}", POD,
            f"🎯 [Tenant {label}] Dedicated Workload Logs", f"Logs from {ns}"))
    scopes += [
        ("security", "dashboard-security-zerotrust", "🛡️ Darueira Security & Zero-Trust Audit",
         "Authentication, authorization, secrets access and ingress security (APISIX, Keycloak, Authentik, OpenFGA, OpenBao, SPIRE)",
         f"{POD}: (apisix* OR authentik* OR keycloak* OR openfga* OR openbao* OR spire*)", POD,
         "🛡️ [Security & Zero-Trust] APISIX, Keycloak, OpenFGA, Vault", "Authentication, authorization and ingress security stream"),
        ("cicd", "dashboard-cicd-gitops", "⚙️ CI/CD & GitOps - Forgejo, Tekton, ArgoCD & Nexus",
         "Build and delivery activity: pipelines, webhooks, image registry and GitOps sync",
         f"{POD}: (argocd* OR tekton* OR el-forgejo* OR forgejo* OR nexus*)", POD,
         "⚙️ [CI/CD & GitOps] ArgoCD, Tekton & Forgejo Logs", "Activity logs from ArgoCD, Tekton, Forgejo and Nexus"),
        ("data", "dashboard-data-messaging", "💾 Data Stores & Messaging - PostgreSQL, MinIO, RabbitMQ, Redpanda, Temporal, NiFi",
         "Persistence, brokers and workflow engines (PostgreSQL is the only tenant database, ADR-0018/0019)",
         f"{POD}: (central-postgres* OR central-minio* OR tenant-postgres* OR tenant-minio* OR message-broker* OR redpanda* OR kafka* OR temporal* OR apache-nifi*)", POD,
         "💾 [Data & Messaging] PostgreSQL, MinIO, brokers, Temporal, NiFi", "Database, object store, broker and workflow engine logs"),
        ("errors", "dashboard-errors-triage", "🚨 Errors Triage - Where Is the Platform Complaining?",
         "Application errors (ERROR, Exception, FATAL, panic) across every namespace, to find the noisy and the broken workloads",
         ERR, NS,
         "🚨 [Errors] ERROR, Exception, FATAL, panic", "Log lines where the application reported an error"),
    ]
    labels = {"platform": "Platform", "tenants": "Tenant", "europe": "swfabrik-europe", "latam": "swfabrik-latam",
              "security": "Security", "cicd": "CI/CD", "data": "Data & Messaging", "errors": "Cluster"}
    for key, dash_id, title, desc, q, group, s_title, s_desc in scopes:
        objects += scope_objects(key, labels[key], q, group, s_title, s_desc, all_q="*" if key == "errors" else None)
        objects.append(scope_dashboard(key, dash_id, title, desc, q))

    # Searches that have no dashboard of their own
    objects += [
        make_search("search-all-logs", "🔍 [All Logs] Platform & All Tenants", "Raw log stream across all cluster namespaces and workloads", "*"),
        make_search("search-errors-exceptions", "🚨 [Errors & Warnings] Broad Stream (incl. WARN and stderr)",
                    "Wider than the Errors dashboard: WARN, fail* and the whole stderr stream", 'log: (ERROR OR Error OR Exception OR fatal OR panic OR fail* OR WARN) OR stream: "stderr"'),
        make_search("search-persistence-db-logs", "💾 [Persistence] PostgreSQL, MinIO & Nexus Logs", "Central and tenant database and object store logs",
                    f"{POD}: (central-postgres* OR central-minio* OR tenant-postgres* OR tenant-minio* OR nexus*)"),
        make_search("search-messaging-logs", "📨 [Messaging] RabbitMQ, Redpanda, Temporal & NiFi", "Brokers and workflow engines",
                    f"{POD}: (message-broker* OR redpanda* OR kafka* OR temporal* OR apache-nifi*)"),
        make_search("search-caseforce-logs", "⚖️ [CaseForce] LegalHub backend & Fake Agency", "Logs of the CaseForce suite (tenant swfabrik-europe)",
                    f"{POD}: (caseforce* OR fake-legal*)"),
        make_search("search-food-market-logs", "🍽️ [Food Market] Services & front-ends", "Logs of the nine food-market projects (tenant swfabrik-europe)",
                    f"{POD}: (food-market* OR app-food-market*)"),
    ]
    return objects

if __name__ == "__main__":
    bundle = generate_bundle()
    output_dir = os.path.join(os.path.dirname(__file__), "..", "platform", "kustomize", "base", "corpshared-obs", "dashboards")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "opensearch-saved-objects.ndjson")
    
    with open(output_file, "w", encoding="utf-8") as f:
        for obj in bundle:
            f.write(json.dumps(obj) + "\n")
    
    print(f"✅ Generated {len(bundle)} saved objects into {output_file}")
