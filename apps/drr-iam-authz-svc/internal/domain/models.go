package domain

import (
	"time"
)

// MutationAction defines the tuple mutation operation
type MutationAction string

const (
	ActionInsert MutationAction = "INSERT"
	ActionDelete MutationAction = "DELETE"
)

// Tuple represents an authorization relationship tuple
type Tuple struct {
	User     string `json:"user"`
	Relation string `json:"relation"`
	Object   string `json:"object"`
}

// PermissionCheckRequest represents an authorization query
type PermissionCheckRequest struct {
	User             string  `json:"user"`
	Relation         string  `json:"relation"`
	Object           string  `json:"object"`
	ContextualTuples []Tuple `json:"contextual_tuples,omitempty"`
}

// PermissionCheckResponse represents the decision output
type PermissionCheckResponse struct {
	Allowed    bool   `json:"allowed"`
	Resolution string `json:"resolution,omitempty"`
}

// BatchCheckRequest represents multiple authorization queries
type BatchCheckRequest struct {
	Checks []PermissionCheckRequest `json:"checks"`
}

// BatchCheckResponse represents the decisions for a batch
type BatchCheckResponse struct {
	Results []PermissionCheckResponse `json:"results"`
}

// TupleMutationEvent represents an event received from message broker (e.g. Kafka)
type TupleMutationEvent struct {
	EventID   string         `json:"event_id"`
	Timestamp time.Time      `json:"timestamp"`
	Action    MutationAction `json:"action"`
	Tuple     Tuple          `json:"tuple"`
}

// TokenClaims represents extracted and validated claims from OIDC JWT
type TokenClaims struct {
	Subject   string   `json:"sub"`
	Email     string   `json:"email"`
	Preferred string   `json:"preferred_username,omitempty"`
	TenantID  string   `json:"tenant_id,omitempty"`
	Roles     []string `json:"roles,omitempty"`
	Groups    []string `json:"groups,omitempty"`
	IssuedAt  int64    `json:"iat"`
	ExpiresAt int64    `json:"exp"`
}
