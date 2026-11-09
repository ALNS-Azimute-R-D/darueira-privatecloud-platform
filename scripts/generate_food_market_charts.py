#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/generate_food_market_charts.py
Purpose: Generates one Helm chart per food-market project (6 services + 3 front-ends) of tenant swfabrik-europe,
         next to the project, as `<repo>-chart/` (the layout ArgoCD expects: chart at the repo root, values.yaml +
         values-dev-green.yaml). The chart is derived from the project's own `k8s/deployment.yaml`:
           - the image becomes Nexus + a `tag:` that the Tekton task `task-gitops-helm-promote` rewrites,
           - literal credentials become $(DB_USER)/$(DB_PASSWORD)/$(MQ_USER)/$(MQ_PASSWORD), read from the secrets
             `food-market-db` and `food-market-mq` that scripts/bootstrap_food_market_data.py creates,
           - ports, probes, resources and the rest of the environment are kept.
Usage:   python3 scripts/generate_food_market_charts.py
==============================================================================
"""

import os
import sys

import yaml

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workspace", "platf-bizz-apps", "swfabrik-europe")
REGISTRY = "nexus-oss.drr-corpshared-plat.svc.cluster.local:8082/swfabrik-europe"
PROJECTS = [
    "food-market-01-service", "food-market-02-service", "food-market-03-service",
    "food-market-04-service", "food-market-05-service", "food-market-06-service",
    "app-food-market-00-mfe", "app-food-market-01-react", "app-food-market-02-angular",
]
DB_LITERAL = "drr_tnt_svcs_admin:tenant_pg_secure_pass_2026"


def rewrite_env(env):
    """Keeps the environment, replacing literal credentials with references to the secret-backed variables."""
    out = []
    for item in env or []:
        name, value = item["name"], str(item.get("value", ""))
        if DB_LITERAL in value:
            value = value.replace(DB_LITERAL, "$(DB_USER):$(DB_PASSWORD)")
        elif name.endswith("DATASOURCE_USERNAME"):
            value = "$(DB_USER)"
        elif name.endswith("DATASOURCE_PASSWORD"):
            value = "$(DB_PASSWORD)"
        elif name.startswith(("SPRING_RABBITMQ_", "RABBITMQ_")) and name.endswith(("USERNAME", "USER")):
            value = "$(MQ_USER)"
        elif name.startswith(("SPRING_RABBITMQ_", "RABBITMQ_")) and name.endswith(("PASSWORD", "PASS")):
            value = "$(MQ_PASSWORD)"
        out.append({"name": name, "value": value})
    return out


CHART_YAML = """apiVersion: v2
name: {name}
description: Helm chart of {name} (tenant swfabrik-europe, food-market marketplace)
type: application
version: 0.1.0
appVersion: "1.0.0"
"""

DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{ .Values.name }}}}
  labels:
    {{{{- include "app.labels" . | nindent 4 }}}}
spec:
  replicas: {{{{ .Values.replicaCount }}}}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{{{ .Values.name }}}}
  template:
    metadata:
      labels:
        {{{{- include "app.labels" . | nindent 8 }}}}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: {{{{ .Values.runAsUser }}}}
        runAsGroup: {{{{ .Values.runAsUser }}}}
        fsGroup: {{{{ .Values.runAsUser }}}}
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: app
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag }}}}"
          imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: false
            capabilities:
              drop:
                - ALL
            seccompProfile:
              type: RuntimeDefault
          ports:
            - containerPort: {{{{ .Values.containerPort }}}}
              name: http
          {{{{- if or .Values.useDatabase .Values.env }}}}
          env:
            {{{{- if .Values.useDatabase }}}}
            # Credentials come from the secrets created by scripts/bootstrap_food_market_data.py (not in Git).
            - name: DB_USER
              valueFrom: {{ secretKeyRef: {{ name: food-market-db, key: username }} }}
            - name: DB_PASSWORD
              valueFrom: {{ secretKeyRef: {{ name: food-market-db, key: password }} }}
            - name: MQ_USER
              valueFrom: {{ secretKeyRef: {{ name: food-market-mq, key: username }} }}
            - name: MQ_PASSWORD
              valueFrom: {{ secretKeyRef: {{ name: food-market-mq, key: password }} }}
            {{{{- end }}}}
            {{{{- with .Values.env }}}}
            {{{{- toYaml . | nindent 12 }}}}
            {{{{- end }}}}
          {{{{- end }}}}
          resources:
            {{{{- toYaml .Values.resources | nindent 12 }}}}
          {{{{- with .Values.startupProbe }}}}
          startupProbe:
            {{{{- toYaml . | nindent 12 }}}}
          {{{{- end }}}}
          livenessProbe:
            {{{{- toYaml .Values.livenessProbe | nindent 12 }}}}
          readinessProbe:
            {{{{- toYaml .Values.readinessProbe | nindent 12 }}}}
      {{{{- with .Values.nodeSelector }}}}
      nodeSelector:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
"""

SERVICE = """apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.name }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: {{ .Values.name }}
  ports:
    - name: http
      port: {{ .Values.service.port }}
      targetPort: {{ .Values.containerPort }}
"""

HELPERS = """{{- define "app.labels" -}}
app.kubernetes.io/name: {{ .Values.name }}
app.kubernetes.io/part-of: swfabrik-europe-marketplaces
app.kubernetes.io/managed-by: {{ .Release.Service }}
darueira.io/tier: tenant-workload
darueira.io/tenant: {{ .Values.tenant }}
darueira.io/project: marketplaces
darueira.io/env: {{ .Values.env_name }}
{{- end -}}
"""


def build(project):
    src = os.path.join(ROOT, project, "k8s", "deployment.yaml")
    docs = list(yaml.safe_load_all(open(src)))
    dep = next(d for d in docs if d["kind"] == "Deployment")
    svc = next(d for d in docs if d["kind"] == "Service")
    pod = dep["spec"]["template"]["spec"]
    c = pod["containers"][0]
    env = rewrite_env(c.get("env"))
    uses_db = any("$(DB_" in e["value"] for e in env)
    values = {
        "name": project,
        "tenant": "swfabrik-europe",
        "env_name": "dev",
        "replicaCount": dep["spec"].get("replicas", 1),
        "runAsUser": pod["securityContext"].get("runAsUser", 10001),
        "image": {"repository": f"{REGISTRY}/{project}", "tag": "0.0.0-bootstrap", "pullPolicy": "IfNotPresent"},
        "containerPort": c["ports"][0]["containerPort"],
        "service": {"port": svc["spec"]["ports"][0]["port"]},
        "useDatabase": uses_db,
        "env": [e for e in env],
        "resources": c["resources"],
        "livenessProbe": c["livenessProbe"],
        "readinessProbe": c["readinessProbe"],
        "nodeSelector": pod.get("nodeSelector", {"kubernetes.io/hostname": "nbalns-mifcom-lnx-01"}),
    }
    if "startupProbe" in c:
        values["startupProbe"] = c["startupProbe"]
    return values


def main():
    for project in PROJECTS:
        chart_dir = os.path.join(ROOT, f"{project}-chart")
        os.makedirs(os.path.join(chart_dir, "templates"), exist_ok=True)
        values = build(project)
        header = ("# Defaults. The image `tag:` is rewritten in values-dev-green.yaml by the Tekton task\n"
                  "# `task-gitops-helm-promote`; credentials come from secrets, never from this file.\n")
        with open(os.path.join(chart_dir, "Chart.yaml"), "w") as f:
            f.write(CHART_YAML.format(name=project))
        with open(os.path.join(chart_dir, "values.yaml"), "w") as f:
            f.write(header + yaml.safe_dump(values, sort_keys=False, default_flow_style=False))
        with open(os.path.join(chart_dir, "values-dev-green.yaml"), "w") as f:
            f.write("# Rewritten by Tekton (task-gitops-helm-promote) after each successful build.\n"
                    f"image:\n  tag: \"0.0.0-bootstrap\"\n")
        with open(os.path.join(chart_dir, "templates", "deployment.yaml"), "w") as f:
            f.write(DEPLOYMENT.format())
        with open(os.path.join(chart_dir, "templates", "service.yaml"), "w") as f:
            f.write(SERVICE)
        with open(os.path.join(chart_dir, "templates", "_helpers.tpl"), "w") as f:
            f.write(HELPERS)
        print(f"[+] {project}-chart  (port {values['containerPort']}, database={values['useDatabase']})")


if __name__ == "__main__":
    sys.exit(main())
