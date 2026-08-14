package domain

import (
	"errors"
	"strings"
	"time"
)

type TenantStatus string

const (
	TenantStatusActive     TenantStatus = "ACTIVE"
	TenantStatusSuspended  TenantStatus = "SUSPENDED"
	TenantStatusTerminated TenantStatus = "TERMINATED"
)

type ResourceQuotas struct {
	MaxCPUCores     int   `json:"maxCpuCores"`
	MaxMemoryGiB    int   `json:"maxMemoryGiB"`
	MaxStorageGiB   int   `json:"maxStorageGiB"`
	MaxEnvironments int   `json:"maxEnvironments"`
	MaxProjects     int   `json:"maxProjects"`
}

func DefaultQuotas() ResourceQuotas {
	return ResourceQuotas{
		MaxCPUCores:     32,
		MaxMemoryGiB:    64,
		MaxStorageGiB:   500,
		MaxEnvironments: 10,
		MaxProjects:     5,
	}
}

type Tenant struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	DisplayName string            `json:"displayName"`
	Description string            `json:"description"`
	Status      TenantStatus      `json:"status"`
	Quotas      ResourceQuotas    `json:"quotas"`
	Labels      map[string]string `json:"labels,omitempty"`
	CreatedAt   time.Time         `json:"createdAt"`
	UpdatedAt   time.Time         `json:"updatedAt"`
}

func NewTenant(id, name, displayName, description string, quotas *ResourceQuotas, labels map[string]string) (*Tenant, error) {
	cleanID := strings.ToLower(strings.TrimSpace(id))
	cleanName := strings.ToLower(strings.TrimSpace(name))

	if cleanID == "" {
		return nil, errors.New("tenant id cannot be empty")
	}
	if cleanName == "" {
		return nil, errors.New("tenant name cannot be empty")
	}
	if displayName == "" {
		displayName = name
	}

	q := DefaultQuotas()
	if quotas != nil {
		q = *quotas
	}

	now := time.Now().UTC()
	return &Tenant{
		ID:          cleanID,
		Name:        cleanName,
		DisplayName: displayName,
		Description: description,
		Status:      TenantStatusActive,
		Quotas:      q,
		Labels:      labels,
		CreatedAt:   now,
		UpdatedAt:   now,
	}, nil
}

func (t *Tenant) Suspend() {
	t.Status = TenantStatusSuspended
	t.UpdatedAt = time.Now().UTC()
}

func (t *Tenant) Activate() {
	t.Status = TenantStatusActive
	t.UpdatedAt = time.Now().UTC()
}

func (t *Tenant) Terminate() {
	t.Status = TenantStatusTerminated
	t.UpdatedAt = time.Now().UTC()
}

func (t *Tenant) UpdateQuotas(quotas ResourceQuotas) {
	t.Quotas = quotas
	t.UpdatedAt = time.Now().UTC()
}
