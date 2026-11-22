{{- define "caseforce.labels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/component: {{ .component }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
helm.sh/chart: {{ .root.Chart.Name }}-{{ .root.Chart.Version }}
darueira.io/tier: tenant-workload
darueira.io/tenant: {{ .root.Values.tenant }}
{{- end -}}

{{/* Selector labels are immutable on a live Deployment: keep them exactly as the cluster has them. */}}
{{- define "caseforce.selector" -}}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/name: {{ .name }}
darueira.io/tenant: {{ .root.Values.tenant }}
{{- end -}}
