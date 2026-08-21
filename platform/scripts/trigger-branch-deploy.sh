#!/usr/bin/env bash
set -eo pipefail

APP_NAME=""
BRANCH="master"
TARGET_ENV="dev-green"
TENANT="swfabrik-europe"
WATCH=false

usage() {
  echo "=================================================================="
  echo "  Darueira Private Cloud - On-Demand Branch & Env Deployer"
  echo "=================================================================="
  echo "Usage: $0 -a <app-name> [-b <branch-name>] [-e <environment>] [-t <tenant>] [--watch]"
  echo ""
  echo "Options:"
  echo "  -a, --app       Application/Service name (e.g. food-market-01-service, app-food-market-00-mfe)"
  echo "  -b, --branch    Git Branch to build and deploy (default: master)"
  echo "  -e, --env       Target environment (default: dev-green, options: dev-green, stg-green, prd-green)"
  echo "  -t, --tenant    Tenant organization (default: swfabrik-europe)"
  echo "  -w, --watch     Follow pipeline execution logs in real-time"
  echo "  -h, --help      Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0 -a food-market-01-service -b feature/market-discount -e dev-green"
  echo "  $0 -a app-food-market-01-react -b master -e dev-green --watch"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    -a|--app) APP_NAME="$2"; shift 2 ;;
    -b|--branch) BRANCH="$2"; shift 2 ;;
    -e|--env) TARGET_ENV="$2"; shift 2 ;;
    -t|--tenant) TENANT="$2"; shift 2 ;;
    -w|--watch) WATCH=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown parameter: $1"; usage ;;
  esac
done

if [ -z "$APP_NAME" ]; then
  echo "Error: --app (-a) parameter is mandatory."
  usage
fi

VALUES_FILE="values-${TARGET_ENV}.yaml"
GIT_HOST="forgejo-git.drr-corpshared-plat.svc.cluster.local:3000"
GIT_URL="http://${GIT_HOST}/${TENANT}/${APP_NAME}.git"
ARGOCD_APP="${TENANT}-${APP_NAME}"

echo "=================================================================="
echo "  Triggering On-Demand CI/CD Deployment"
echo "  Tenant      : $TENANT"
echo "  Application : $APP_NAME"
echo "  Branch      : $BRANCH"
echo "  Target Env  : $TARGET_ENV"
echo "  Values File : $VALUES_FILE"
echo "  ArgoCD App  : $ARGOCD_APP"
echo "=================================================================="

RUN_NAME="manual-ci-${APP_NAME}-$(date +%s)"

cat <<YAML | kubectl create -f -
apiVersion: tekton.dev/v1beta1
kind: PipelineRun
metadata:
  name: ${RUN_NAME}
  namespace: drr-corpshared-mgmt
  labels:
    darueira.io/tier: enterprise-shared
    darueira.io/triggered-by: on-demand-cli
    darueira.io/tenant: ${TENANT}
    app.kubernetes.io/name: ${APP_NAME}
spec:
  pipelineRef:
    name: standard-ci-cd-pipeline
  params:
    - name: git-url
      value: "${GIT_URL}"
    - name: git-revision
      value: "${BRANCH}"
    - name: image-name
      value: "nexus-oss.drr-corpshared-plat.svc.cluster.local:8082/${TENANT}/${APP_NAME}"
    - name: image-tag
      value: "auto"
    - name: tenant-name
      value: "${TENANT}"
    - name: app-name
      value: "${APP_NAME}"
    - name: target-env
      value: "${TARGET_ENV}"
    - name: values-file
      value: "${VALUES_FILE}"
    - name: argocd-app-name
      value: "${ARGOCD_APP}"
  workspaces:
    - name: pipeline-workspace
      volumeClaimTemplate:
        spec:
          accessModes:
            - ReadWriteOnce
          resources:
            requests:
              storage: 1Gi
YAML

echo "==> PipelineRun '${RUN_NAME}' successfully launched in drr-corpshared-mgmt!"

if [ "$WATCH" = true ]; then
  echo "==> Watching pipeline execution..."
  while true; do
    STATUS=$(kubectl get pipelinerun "${RUN_NAME}" -n drr-corpshared-mgmt -o jsonpath='{.status.conditions[0].status}' 2>/dev/null || echo "Unknown")
    REASON=$(kubectl get pipelinerun "${RUN_NAME}" -n drr-corpshared-mgmt -o jsonpath='{.status.conditions[0].reason}' 2>/dev/null || echo "Running")
    
    echo "  [$(date +%H:%M:%S)] PipelineRun Status: $STATUS ($REASON)"
    
    if [ "$STATUS" = "True" ]; then
      echo "==> [SUCCESS] PipelineRun finished successfully!"
      break
    elif [ "$STATUS" = "False" ]; then
      echo "==> [FAILED] PipelineRun failed: $REASON"
      exit 1
    fi
    sleep 5
  done
fi
