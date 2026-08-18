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

def generate_bundle():
    objects = []

    # 1. Index Pattern
    objects.append(make_index_pattern())

    # 2. Saved Searches (Discover Pre-saved Queries)
    searches = [
        ("search-all-logs", "🔍 [All Logs] Platform & All Tenants", "Raw log stream across all cluster namespaces and workloads", "*"),
        ("search-platform-logs", "🏢 [Platform] Enterprise Shared Services Logs", "Logs strictly from drr-corpshared-* namespaces (plat, mgmt, secr, obs)", "kubernetes.namespace_name: drr-corpshared-*"),
        ("search-tenants-all-logs", "👥 [Tenants] All Multi-Tenant Workload Logs", "Logs strictly from all tenant environments (drr-tnt-*)", "kubernetes.namespace_name: drr-tnt-*"),
        ("search-tenant-acme-logs", "🎯 [Tenant ACME] Dedicated Workload Logs", "Logs from Tenant ACME (drr-tnt-acme)", "kubernetes.namespace_name: drr-tnt-acme"),
        ("search-errors-exceptions", "🚨 [Errors & Warnings] Critical Log Stream", "Aggregated errors, exceptions, fatals, panics and stderr streams", "log: (ERROR OR Error OR Exception OR fatal OR panic OR fail* OR WARN) OR stream: \"stderr\""),
        ("search-cicd-gitops-logs", "⚙️ [CI/CD & GitOps] ArgoCD, Tekton & Forgejo Logs", "Activity logs from ArgoCD, Tekton Pipelines, Forgejo Git, and Nexus", "kubernetes.pod_name: (argocd* OR tekton* OR el-forgejo* OR forgejo* OR nexus*)"),
        ("search-security-authz-logs", "🛡️ [Security & Zero-Trust] APISIX, Keycloak, OpenFGA, Vault", "Authentication, authorization, and ingress security stream", "kubernetes.pod_name: (apisix* OR authentik* OR keycloak* OR openfga* OR openbao* OR spire*)"),
        ("search-persistence-db-logs", "💾 [Persistence] Postgres, MinIO & MongoDB Logs", "Central & Tenant database and object store persistence logs", "kubernetes.pod_name: (central-postgres* OR central-minio* OR tenant-postgres* OR tenant-minio* OR tenant-mongodb*)")
    ]

    for sid, title, desc, q in searches:
        objects.append(make_search(sid, title, desc, q))

    # 3. Visualizations
    # Platform Visualizations
    objects.append(make_vis_histogram("vis-platform-log-timeline", "Platform Services Log Volume (Timeline)", "kubernetes.namespace_name: drr-corpshared-*", "kubernetes.namespace_name.keyword"))
    objects.append(make_vis_pie("vis-platform-namespace-share", "Platform Namespaces Breakdown", "kubernetes.namespace_name: drr-corpshared-*", "kubernetes.namespace_name.keyword"))
    objects.append(make_vis_horizontal_bar("vis-platform-top-pods", "Top Platform Pods by Volume", "kubernetes.namespace_name: drr-corpshared-*", "kubernetes.pod_name.keyword", 15))
    objects.append(make_vis_histogram("vis-platform-errors-timeline", "Platform Errors & Warnings Timeline", "kubernetes.namespace_name: drr-corpshared-* AND (log: (ERROR OR Error OR Exception OR fatal OR panic OR fail*) OR stream: \"stderr\")", "kubernetes.pod_name.keyword"))
    objects.append(make_vis_metric("vis-platform-total-logs", "Total Platform Logs", "kubernetes.namespace_name: drr-corpshared-*", "Platform Logs"))
    objects.append(make_vis_metric("vis-platform-total-errors", "Total Platform Errors", "kubernetes.namespace_name: drr-corpshared-* AND (log: (ERROR OR Error OR Exception OR fatal OR panic OR fail*) OR stream: \"stderr\")", "Platform Errors"))

    # Tenants Visualizations
    objects.append(make_vis_histogram("vis-tenants-log-timeline", "All Tenants Log Activity Timeline", "kubernetes.namespace_name: drr-tnt-*", "kubernetes.namespace_name.keyword"))
    objects.append(make_vis_pie("vis-tenants-namespace-share", "Tenant Workload Distribution", "kubernetes.namespace_name: drr-tnt-*", "kubernetes.namespace_name.keyword"))
    objects.append(make_vis_horizontal_bar("vis-tenants-top-pods", "Top Tenant Pods by Log Volume", "kubernetes.namespace_name: drr-tnt-*", "kubernetes.pod_name.keyword", 15))
    objects.append(make_vis_histogram("vis-tenants-errors-timeline", "Tenants Errors & Warnings Timeline", "kubernetes.namespace_name: drr-tnt-* AND (log: (ERROR OR Error OR Exception OR fatal OR panic OR fail*) OR stream: \"stderr\")", "kubernetes.namespace_name.keyword"))
    objects.append(make_vis_metric("vis-tenants-total-logs", "Total Tenant Logs", "kubernetes.namespace_name: drr-tnt-*", "Tenant Logs"))
    objects.append(make_vis_metric("vis-tenants-total-errors", "Total Tenant Errors", "kubernetes.namespace_name: drr-tnt-* AND (log: (ERROR OR Error OR Exception OR fatal OR panic OR fail*) OR stream: \"stderr\")", "Tenant Errors"))

    # Tenant ACME Visualizations
    objects.append(make_vis_histogram("vis-tenant-acme-timeline", "Tenant ACME Pod Log Timeline", "kubernetes.namespace_name: drr-tnt-acme", "kubernetes.pod_name.keyword"))
    objects.append(make_vis_pie("vis-tenant-acme-pods-share", "Tenant ACME Component Breakdown", "kubernetes.namespace_name: drr-tnt-acme", "kubernetes.pod_name.keyword"))
    objects.append(make_vis_horizontal_bar("vis-tenant-acme-pods-bar", "Tenant ACME Pods Activity", "kubernetes.namespace_name: drr-tnt-acme", "kubernetes.pod_name.keyword", 10))
    objects.append(make_vis_histogram("vis-tenant-acme-errors-timeline", "Tenant ACME Error Timeline", "kubernetes.namespace_name: drr-tnt-acme AND (log: (ERROR OR Error OR Exception OR fatal OR panic OR fail*) OR stream: \"stderr\")", "kubernetes.pod_name.keyword"))
    objects.append(make_vis_metric("vis-tenant-acme-total-logs", "Tenant ACME Total Logs", "kubernetes.namespace_name: drr-tnt-acme", "ACME Logs"))
    objects.append(make_vis_metric("vis-tenant-acme-total-errors", "Tenant ACME Total Errors", "kubernetes.namespace_name: drr-tnt-acme AND (log: (ERROR OR Error OR Exception OR fatal OR panic OR fail*) OR stream: \"stderr\")", "ACME Errors"))

    # Security & Zero-Trust Visualizations
    objects.append(make_vis_histogram("vis-security-events-timeline", "Security & Zero-Trust Events Timeline", "kubernetes.pod_name: (apisix* OR authentik* OR keycloak* OR openfga* OR openbao* OR spire*)", "kubernetes.pod_name.keyword"))
    objects.append(make_vis_pie("vis-security-components-share", "Security Components Log Share", "kubernetes.pod_name: (apisix* OR authentik* OR keycloak* OR openfga* OR openbao* OR spire*)", "kubernetes.pod_name.keyword"))
    objects.append(make_vis_horizontal_bar("vis-security-top-pods", "Top Security Workloads", "kubernetes.pod_name: (apisix* OR authentik* OR keycloak* OR openfga* OR openbao* OR spire*)", "kubernetes.pod_name.keyword", 10))
    objects.append(make_vis_metric("vis-security-total-events", "Total Security Events", "kubernetes.pod_name: (apisix* OR authentik* OR keycloak* OR openfga* OR openbao* OR spire*)", "Security Events"))

    # 4. Dashboards
    # Dashboard 1: Platform Overview
    dash_platform_panels = [
        (1, "visualization", "vis-platform-total-logs", 0, 0, 12, 6),
        (2, "visualization", "vis-platform-total-errors", 12, 0, 12, 6),
        (3, "visualization", "vis-platform-log-timeline", 0, 6, 24, 12),
        (4, "visualization", "vis-platform-namespace-share", 0, 18, 12, 12),
        (5, "visualization", "vis-platform-top-pods", 12, 18, 12, 12),
        (6, "visualization", "vis-platform-errors-timeline", 0, 30, 24, 12),
        (7, "search", "search-platform-logs", 0, 42, 24, 16)
    ]
    objects.append(make_dashboard(
        "dashboard-platform-overview",
        "🏢 Darueira Platform - Enterprise Control Plane Overview",
        "Comprehensive observability dashboard for all Corporate Shared Services (Security, Platform, Obs, Mgmt)",
        dash_platform_panels,
        "kubernetes.namespace_name: drr-corpshared-*"
    ))

    # Dashboard 2: Tenants Overview
    dash_tenants_panels = [
        (1, "visualization", "vis-tenants-total-logs", 0, 0, 12, 6),
        (2, "visualization", "vis-tenants-total-errors", 12, 0, 12, 6),
        (3, "visualization", "vis-tenants-log-timeline", 0, 6, 24, 12),
        (4, "visualization", "vis-tenants-namespace-share", 0, 18, 12, 12),
        (5, "visualization", "vis-tenants-top-pods", 12, 18, 12, 12),
        (6, "visualization", "vis-tenants-errors-timeline", 0, 30, 24, 12),
        (7, "search", "search-tenants-all-logs", 0, 42, 24, 16)
    ]
    objects.append(make_dashboard(
        "dashboard-tenants-overview",
        "👥 Darueira Tenants - Multi-Tenant Workloads Overview",
        "Aggregated log and health overview across all tenant namespaces (drr-tnt-*)",
        dash_tenants_panels,
        "kubernetes.namespace_name: drr-tnt-*"
    ))

    # Dashboard 3: Tenant Deep-Dive (ACME)
    dash_tenant_acme_panels = [
        (1, "visualization", "vis-tenant-acme-total-logs", 0, 0, 12, 6),
        (2, "visualization", "vis-tenant-acme-total-errors", 12, 0, 12, 6),
        (3, "visualization", "vis-tenant-acme-timeline", 0, 6, 24, 12),
        (4, "visualization", "vis-tenant-acme-pods-share", 0, 18, 12, 12),
        (5, "visualization", "vis-tenant-acme-pods-bar", 12, 18, 12, 12),
        (6, "visualization", "vis-tenant-acme-errors-timeline", 0, 30, 24, 12),
        (7, "search", "search-tenant-acme-logs", 0, 42, 24, 16)
    ]
    objects.append(make_dashboard(
        "dashboard-tenant-acme-deepdive",
        "🎯 Tenant Deep-Dive - ACME Corporation (drr-tnt-acme)",
        "Focused observability for Tenant ACME workloads (tenant-postgres, tenant-minio, tenant-keycloak, tenant-openbao, tenant-mongodb)",
        dash_tenant_acme_panels,
        "kubernetes.namespace_name: drr-tnt-acme"
    ))

    # Dashboard 4: Security & Zero-Trust Audit
    dash_security_panels = [
        (1, "visualization", "vis-security-total-events", 0, 0, 24, 6),
        (2, "visualization", "vis-security-events-timeline", 0, 6, 24, 12),
        (3, "visualization", "vis-security-components-share", 0, 18, 12, 12),
        (4, "visualization", "vis-security-top-pods", 12, 18, 12, 12),
        (5, "search", "search-security-authz-logs", 0, 30, 24, 16)
    ]
    objects.append(make_dashboard(
        "dashboard-security-zerotrust",
        "🛡️ Darueira Security & Zero-Trust Audit",
        "Authentication, authorization, secrets access, and ingress security log analysis (APISIX, Keycloak, OpenFGA, Vault, SPIRE)",
        dash_security_panels,
        "kubernetes.pod_name: (apisix* OR authentik* OR keycloak* OR openfga* OR openbao* OR spire*)"
    ))

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
