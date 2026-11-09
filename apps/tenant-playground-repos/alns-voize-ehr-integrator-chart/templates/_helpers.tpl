{{/* The resource name is fixed on purpose: ArgoCD adopts the objects that already exist in the namespace. */}}
{{- define "alns-voize-ehr-integrator.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "alns-voize-ehr-integrator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "alns-voize-ehr-integrator.name" . }}
{{- end -}}

{{- define "alns-voize-ehr-integrator.labels" -}}
{{ include "alns-voize-ehr-integrator.selectorLabels" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
darueira.io/env: {{ .Values.env }}
darueira.io/project: {{ .Values.project }}
darueira.io/tenant: {{ .Values.tenant }}
darueira.io/tier: tenant-workload
{{- end -}}
