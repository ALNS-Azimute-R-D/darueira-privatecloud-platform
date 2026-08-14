package domain

import "time"

type PipelineRun struct {
	ID          string    `json:"id"`
	TenantID    string    `json:"tenantId"`
	ProjectID   string    `json:"projectId"`
	EnvID       string    `json:"envId"`
	Status      string    `json:"status"` // Succeeded, Running, Failed
	CommitHash  string    `json:"commitHash"`
	TriggeredBy string    `json:"triggeredBy"`
	StartTime   time.Time `json:"startTime"`
	EndTime     time.Time `json:"endTime,omitempty"`
}

type GitOpsSync struct {
	AppName       string    `json:"appName"`
	Namespace     string    `json:"namespace"`
	SyncStatus    string    `json:"syncStatus"` // Synced, OutOfSync
	HealthStatus  string    `json:"healthStatus"` // Healthy, Degraded, Progressing
	LastSyncedAt  time.Time `json:"lastSyncedAt"`
}
