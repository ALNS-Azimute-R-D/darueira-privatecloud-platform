package domain

import (
	"time"
)

type EventType string

const (
	EventTypeTenantCreated        EventType = "tenant.created"
	EventTypeTenantUpdated        EventType = "tenant.updated"
	EventTypeTenantStatusChanged  EventType = "tenant.status_changed"
	EventTypeTenantDeleted        EventType = "tenant.deleted"
	EventTypeProjectCreated       EventType = "project.created"
	EventTypeProjectDeleted       EventType = "project.deleted"
	EventTypeMemberAssigned       EventType = "member.assigned"
	EventTypeMemberRemoved        EventType = "member.removed"
)

type DomainEvent struct {
	ID        string      `json:"id"`
	Type      EventType   `json:"type"`
	TenantID  string      `json:"tenantId"`
	Payload   interface{} `json:"payload"`
	Timestamp time.Time   `json:"timestamp"`
}

type EventPublisher interface {
	Publish(event DomainEvent) error
}
