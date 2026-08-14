package domain

import "time"

type EventType string

const (
	EventTypeEnvironmentCreated     EventType = "environment.created"
	EventTypeEnvironmentProvisioned EventType = "environment.provisioned"
	EventTypeEnvironmentDeploying   EventType = "environment.deploying"
	EventTypeEnvironmentActive      EventType = "environment.active"
	EventTypeEnvironmentDeleted     EventType = "environment.deleted"
	EventTypePipelineTriggered      EventType = "pipeline.triggered"
)

type DomainEvent struct {
	ID        string      `json:"id"`
	Type      EventType   `json:"type"`
	TenantID  string      `json:"tenantId"`
	ProjectID string      `json:"projectId"`
	EnvID     string      `json:"envId"`
	Payload   interface{} `json:"payload"`
	Timestamp time.Time   `json:"timestamp"`
}

type EventPublisher interface {
	Publish(event DomainEvent) error
}
