{{- define "bookanything.labels" -}}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .root.Chart.Name .root.Chart.Version }}
darueira.io/env: {{ .root.Values.env }}
darueira.io/project: {{ .root.Values.project }}
darueira.io/tenant: {{ .root.Values.tenant }}
darueira.io/tier: tenant-workload
{{- end -}}

{{/* Init container: logs in to the tenant OpenBao with AppRole and writes `export` lines for the app. */}}
{{- define "bookanything.openbaoInit" -}}
- name: openbao-secrets
  image: {{ .Values.openbao.image }}
  imagePullPolicy: IfNotPresent
  securityContext:
    {{- toYaml .Values.containerSecurityContext | nindent 4 }}
  env:
    - name: VAULT_ADDR
      value: {{ .Values.openbao.address | quote }}
    - name: HOME
      value: /tmp
    - name: ROLE_ID
      valueFrom: {secretKeyRef: {name: {{ .Values.openbao.approleSecret }}, key: role_id}}
    - name: SECRET_ID
      valueFrom: {secretKeyRef: {name: {{ .Values.openbao.approleSecret }}, key: secret_id}}
  command: ["sh", "-c"]
  args:
    - |
      set -eu
      VAULT_TOKEN="$(vault write -field=token auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"
      export VAULT_TOKEN
      umask 077
      {
        echo "export GEMINI_API_KEY='$(vault kv get -field=api_key {{ .Values.openbao.geminiPath | replace "secret/" "-mount=secret " }})'"
        echo "export KEYCLOAK_CLIENT_SECRET='$(vault kv get -field=client_secret {{ .Values.openbao.keycloakPath | replace "secret/" "-mount=secret " }})'"
      } > /secrets/env
      echo "secrets written"
  volumeMounts:
    - {name: secrets, mountPath: /secrets}
    - {name: tmp, mountPath: /tmp}
{{- end -}}
