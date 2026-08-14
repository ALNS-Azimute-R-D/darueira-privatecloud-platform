package domain

import (
	"errors"
	"strings"
	"time"
)

type ProjectStatus string

const (
	ProjectStatusActive   ProjectStatus = "ACTIVE"
	ProjectStatusArchived ProjectStatus = "ARCHIVED"
)

type Project struct {
	ID          string            `json:"id"`
	TenantID    string            `json:"tenantId"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Status      ProjectStatus     `json:"status"`
	Labels      map[string]string `json:"labels,omitempty"`
	CreatedAt   time.Time         `json:"createdAt"`
	UpdatedAt   time.Time         `json:"updatedAt"`
}

func NewProject(id, tenantID, name, description string, labels map[string]string) (*Project, error) {
	cleanID := strings.ToLower(strings.TrimSpace(id))
	cleanTenantID := strings.ToLower(strings.TrimSpace(tenantID))
	cleanName := strings.ToLower(strings.TrimSpace(name))

	if cleanID == "" {
		return nil, errors.New("project id cannot be empty")
	}
	if cleanTenantID == "" {
		return nil, errors.New("tenant id cannot be empty")
	}
	if cleanName == "" {
		return nil, errors.New("project name cannot be empty")
	}

	now := time.Now().UTC()
	return &Project{
		ID:          cleanID,
		TenantID:    cleanTenantID,
		Name:        cleanName,
		Description: description,
		Status:      ProjectStatusActive,
		Labels:      labels,
		CreatedAt:   now,
		UpdatedAt:   now,
	}, nil
}

func (p *Project) Archive() {
	p.Status = ProjectStatusArchived
	p.UpdatedAt = time.Now().UTC()
}

func (p *Project) Activate() {
	p.Status = ProjectStatusActive
	p.UpdatedAt = time.Now().UTC()
}
