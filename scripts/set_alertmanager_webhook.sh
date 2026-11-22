#!/usr/bin/env bash
# Sets the destination of the Alertmanager webhook (Secret alertmanager-webhook, key `url`) and reloads Alertmanager.
# The URL is a secret (Slack/Teams/n8n URLs carry a token): it is read from stdin or from the environment, never from the
# command line, never printed, never written to a file or to Git.
#
# Usage:
#   scripts/set_alertmanager_webhook.sh --sink            # in-cluster test receiver that logs every alert (default install)
#   printf '%s' "$URL" | scripts/set_alertmanager_webhook.sh -      # read the URL from stdin
#   ALERT_WEBHOOK_URL=... scripts/set_alertmanager_webhook.sh -     # or from the environment
# Alertmanager sends its standard webhook JSON (https://prometheus.io/docs/alerting/latest/configuration/#webhook_config).
set -euo pipefail

NS="${NS:-drr-corpshared-obs}"
SECRET="alertmanager-webhook"
SINK_URL="http://alert-webhook-sink.${NS}.svc.cluster.local:8080/alerts"

case "${1:-}" in
  --sink) URL="$SINK_URL" ;;
  -)      URL="${ALERT_WEBHOOK_URL:-}"; [[ -n "$URL" ]] || IFS= read -r URL ;;
  *)      echo "usage: $0 --sink | -   (URL on stdin or in ALERT_WEBHOOK_URL)" >&2; exit 2 ;;
esac
[[ "$URL" =~ ^https?://[^[:space:]]+$ ]] || { echo "the URL must start with http:// or https://" >&2; exit 2; }

kubectl -n "$NS" delete secret "$SECRET" --ignore-not-found >/dev/null
kubectl -n "$NS" create secret generic "$SECRET" --from-file=url=<(printf '%s' "$URL") >/dev/null
kubectl -n "$NS" label secret "$SECRET" app.kubernetes.io/name=alertmanager darueira.io/tier=enterprise-shared --overwrite >/dev/null
echo "secret $SECRET written ($([[ "$URL" == "$SINK_URL" ]] && echo 'in-cluster test sink' || echo 'external URL, not shown'))"

# A mounted Secret reaches the pod after up to ~60 s; reload once it has.
if kubectl -n "$NS" get deploy alertmanager >/dev/null 2>&1; then
  for _ in $(seq 1 40); do
    [[ "$(kubectl -n "$NS" exec deploy/alertmanager -- cat /etc/alertmanager/webhook/url 2>/dev/null || true)" == "$URL" ]] && break
    sleep 3
  done
  kubectl -n "$NS" exec deploy/alertmanager -- wget -qO- --post-data= http://127.0.0.1:9093/-/reload >/dev/null && echo "alertmanager reloaded"
fi
