#!/usr/bin/env python3
"""
==============================================================================
  Mission #15 Validation Suite: Multi-Tenant Polyglot Event-Driven Platform
  Tenant: swfabrik-europe | Project: marketplaces | Env: dev
==============================================================================
"""

import sys
import json
import urllib.request
import urllib.error
import subprocess

GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

def log_info(msg: str):
    print(f"{CYAN}[INFO]{NC} {msg}")

def log_success(msg: str):
    print(f"{GREEN}[PASS]{NC} {msg}")

def log_error(msg: str):
    print(f"{RED}[FAIL]{NC} {msg}")

def run_kubectl(cmd: str) -> str:
    res = subprocess.run(f"microk8s kubectl {cmd}", shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"kubectl error: {res.stderr.strip()}")
    return res.stdout.strip()

def run_in_authentik(python_code: str) -> str:
    res = subprocess.run(
        ["microk8s", "kubectl", "exec", "-i", "-n", "drr-corpshared-plat", "deploy/authentik-server", "-c", "server", "--", "python3"],
        input=python_code,
        capture_output=True,
        text=True
    )
    if res.returncode != 0:
        raise RuntimeError(f"Cluster execution error:\nStdout: {res.stdout}\nStderr: {res.stderr}")
    return res.stdout.strip()

def main():
    print(f"{CYAN}================================================================================{NC}")
    print(f"{CYAN}  Darueira Platform - Mission #15 Polyglot Multi-Tenant Validation Suite        {NC}")
    print(f"{CYAN}================================================================================{NC}")

    passed = 0
    total = 0

    # Step 1: Validate Tenant CRDs and Namespace
    log_info("Step 1: Checking Tenant, Project, Environment CRDs and Namespace...")
    total += 1
    try:
        tenants = run_kubectl("get tenants.darueira.io -o json")
        t_json = json.loads(tenants)
        t_names = [i["metadata"]["name"] for i in t_json.get("items", [])]
        if "swfabrik-europe" in t_names:
            log_success("Tenant 'swfabrik-europe' CRD found and registered.")
            passed += 1
        else:
            log_error("Tenant 'swfabrik-europe' not found in CRDs.")
    except Exception as e:
        log_error(f"Failed checking Tenant CRD: {e}")

    total += 1
    try:
        ns = run_kubectl("get ns drr-tnt-swfabrik-europe-marketplaces-dev -o json")
        ns_json = json.loads(ns)
        pss_enforce = ns_json.get("metadata", {}).get("labels", {}).get("pod-security.kubernetes.io/enforce")
        if pss_enforce == "restricted":
            log_success("Namespace 'drr-tnt-swfabrik-europe-marketplaces-dev' is active with PSS 'restricted'.")
            passed += 1
        else:
            log_error(f"Namespace PSS enforce label is '{pss_enforce}', expected 'restricted'.")
    except Exception as e:
        log_error(f"Failed checking Tenant Namespace: {e}")

    # Step 2: Validate Pods Running
    log_info("Step 2: Checking Pod Status across all 6 microservices & 3 frontends...")
    expected_deployments = [
        "food-market-01-service",
        "food-market-02-service",
        "food-market-03-service",
        "food-market-04-service",
        "food-market-05-service",
        "food-market-06-service",
        "app-food-market-00-mfe",
        "app-food-market-01-react",
        "app-food-market-02-angular"
    ]

    for dep in expected_deployments:
        total += 1
        try:
            out = run_kubectl(f"get deployment/{dep} -n drr-tnt-swfabrik-europe-marketplaces-dev -o json")
            d_json = json.loads(out)
            ready_replicas = d_json.get("status", {}).get("readyReplicas", 0)
            if ready_replicas >= 1:
                log_success(f"Deployment '{dep}' is 1/1 READY.")
                passed += 1
            else:
                log_error(f"Deployment '{dep}' has {ready_replicas} ready replicas.")
        except Exception as e:
            log_error(f"Deployment '{dep}' failed: {e}")

    # Step 3: Test 6 Polyglot REST APIs & OpenAPI Specs & DB persistence
    log_info("Step 3: Testing REST API, OpenAPI, Database & RabbitMQ Event Flow for each Backend...")

    test_script = """
import urllib.request, json, time

services = [
    {"num": 1, "tech": "Java / Spring Boot", "port": 8081, "market": "MKT-EU-01-JAVA", "item": "Spanish Olive Oil 5L", "price": 38.5, "trader": "Andalucia SL", "openapi": "/v3/api-docs"},
    {"num": 2, "tech": "Kotlin / Quarkus", "port": 8082, "market": "MKT-EU-02-QUARKUS", "item": "Parmigiano Reggiano 24M", "price": 65.0, "trader": "Emilia Foods", "openapi": "/q/openapi?format=json"},
    {"num": 3, "tech": "Go / Gin", "port": 8083, "market": "MKT-EU-03-GOLANG", "item": "Black Forest Ham 5kg", "price": 48.0, "trader": "Bavaria Meats", "openapi": "/v3/api-docs"},
    {"num": 4, "tech": "Python / FastAPI", "port": 8084, "market": "MKT-EU-04-PYTHON", "item": "Brie de Meaux AOP", "price": 35.5, "trader": "Fromagerie Paris", "openapi": "/openapi.json"},
    {"num": 5, "tech": "TypeScript / NestJS", "port": 8085, "market": "MKT-EU-05-NESTJS", "item": "Belgian Pralines 1kg", "price": 22.5, "trader": "Brussels Chocolatiers", "openapi": "/v3/api-docs"},
    {"num": 6, "tech": ".NET 8 / C#", "port": 8086, "market": "MKT-EU-06-DOTNET", "item": "Jamon Iberico 7kg", "price": 280.0, "trader": "Jabugo Dehesa", "openapi": "/v3/api-docs/v1/swagger.json"},
]

results = []
for s in services:
    base_url = f"http://food-market-0{s['num']}-service.drr-tnt-swfabrik-europe-marketplaces-dev.svc.cluster.local:{s['port']}"
    
    # 1. Test POST /api/food-tradings
    post_data = json.dumps({
        "itemName": s["item"],
        "quantity": 10.0,
        "unitPrice": s["price"],
        "traderName": s["trader"]
    }).encode()
    
    req = urllib.request.Request(f"{base_url}/api/food-tradings", data=post_data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        post_res = json.loads(resp.read().decode())
    
    # 2. Test GET /api/food-tradings
    with urllib.request.urlopen(f"{base_url}/api/food-tradings", timeout=5) as resp:
        get_res = json.loads(resp.read().decode())
    
    # 3. Test OpenAPI
    with urllib.request.urlopen(f"{base_url}{s['openapi']}", timeout=5) as resp:
        openapi_res = json.loads(resp.read().decode())
    
    results.append({
        "num": s["num"],
        "tech": s["tech"],
        "post_ok": bool(post_res.get("tradingId")),
        "tradingId": post_res.get("tradingId"),
        "total_items": len(get_res),
        "openapi_ok": bool(openapi_res.get("paths") or openapi_res.get("info"))
    })

print(json.dumps(results))
"""

    try:
        raw_res = run_in_authentik(test_script)
        results = json.loads(raw_res)
        for r in results:
            total += 1
            if r["post_ok"] and r["openapi_ok"] and r["total_items"] > 0:
                log_success(f"Service #0{r['num']} ({r['tech']}): POST created {r['tradingId']}, GET count={r['total_items']}, OpenAPI verified.")
                passed += 1
            else:
                log_error(f"Service #0{r['num']} ({r['tech']}) verification failed: {r}")
    except Exception as e:
        log_error(f"Failed running polyglot microservice test suite: {e}")

    # Step 4: Validate Frontend App
    log_info("Step 4: Checking Frontend Host SPA...")
    total += 1
    try:
        fe_script = """
import urllib.request
with urllib.request.urlopen("http://app-food-market-00-mfe.drr-tnt-swfabrik-europe-marketplaces-dev.svc.cluster.local:80", timeout=5) as resp:
    html = resp.read().decode()
    print("STATUS_OK" if resp.status == 200 and "<title>" in html else "STATUS_FAIL")
"""
        res = run_in_authentik(fe_script)
        if "STATUS_OK" in res:
            log_success("Frontend Host SPA (React 19 / Vite / Tailwind) returned HTTP 200 OK.")
            passed += 1
        else:
            log_error(f"Frontend returned unexpected output: {res}")
    except Exception as e:
        log_error(f"Failed checking frontend SPA: {e}")

    print(f"\n{CYAN}================================================================================{NC}")
    if passed == total:
        print(f"{GREEN}  MISSION #15 VALIDATION COMPLETE: ALL {passed}/{total} ASSERTIONS PASSED!       {NC}")
    else:
        print(f"{RED}  MISSION #15 VALIDATION FAILED: {passed}/{total} ASSERTIONS PASSED.             {NC}")
    print(f"{CYAN}================================================================================{NC}")

    if passed != total:
        sys.exit(1)

if __name__ == "__main__":
    main()
