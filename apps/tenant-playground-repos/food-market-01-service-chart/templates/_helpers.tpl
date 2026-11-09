{{- define "app.labels" -}}
app.kubernetes.io/name: {{ .Values.name }}
app.kubernetes.io/part-of: swfabrik-europe-marketplaces
app.kubernetes.io/managed-by: {{ .Release.Service }}
darueira.io/tier: tenant-workload
darueira.io/tenant: {{ .Values.tenant }}
darueira.io/project: marketplaces
darueira.io/env: {{ .Values.env_name }}
{{- end -}}
