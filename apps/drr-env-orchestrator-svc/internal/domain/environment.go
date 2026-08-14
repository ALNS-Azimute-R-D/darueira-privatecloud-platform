package domain

import (
	"errors"
	"fmt"
	"strings"
	"time"
)

type EnvironmentType string

const (
	EnvTypeDev     EnvironmentType = "dev"
	EnvTypeStaging EnvironmentType = "staging"
	EnvTypeProd    EnvironmentType = "prod"
)

type EnvironmentStatus string

const (
	EnvStatusPending     EnvironmentStatus = "PENDING"
	EnvStatusProvisioned EnvironmentStatus = "PROVISIONED"
	EnvStatusDeploying   EnvironmentStatus = "DEPLOYING"
	EnvStatusActive      EnvironmentStatus = "ACTIVE"
	EnvStatusFailed      EnvironmentStatus = "FAILED"
	EnvStatusTerminating EnvironmentStatus = "TERMINATING"
)

type EnvironmentResources struct {
	CPURequest    string `json:"cpuRequest"`
	CPULimit      string `json:"cpuLimit"`
	MemoryRequest string `json:"memoryRequest"`
	MemoryLimit   string `json:"memoryLimit"`
}

func DefaultEnvResources(envType EnvironmentType) EnvironmentResources {
	switch envType {
	case EnvTypeProd:
		return EnvironmentResources{
			CPURequest:    "500m",
			CPULimit:      "2000m",
			MemoryRequest: "1Gi",
			MemoryLimit:   "4Gi",
		}
	case EnvTypeStaging:
		return EnvironmentResources{
			CPURequest:    "250m",
			CPULimit:      "1000m",
			MemoryRequest: "512Mi",
			MemoryLimit:   "2Gi",
		}
	default: // dev
		return EnvironmentResources{
			CPURequest:    "100m",
			CPULimit:      "500m",
			MemoryRequest: "256Mi",
			MemoryLimit:   "1Gi",
		}
	}
}

type Environment struct {
	ID          string               `json:"id"`
	TenantID    string               `json:"tenantId"`
	ProjectID   string               `json:"projectId"`
	Name        string               `json:"name"`
	Type        EnvironmentType      `json:"type"`
	Namespace   string               `json:"namespace"`
	Status      EnvironmentStatus    `json:"status"`
	Resources   EnvironmentResources `json:"resources"`
	Components  []*Component         `json:"components"`
	Labels      map[string]string    `json:"labels,omitempty"`
	CreatedAt   time.Time            `json:"createdAt"`
	UpdatedAt   time.Time            `json:"updatedAt"`
}

func NewEnvironment(tenantID, projectID, name string, envType EnvironmentType, resources *EnvironmentResources, labels map[string]string) (*Environment, error) {
	cleanTenant := strings.ToLower(strings.TrimSpace(tenantID))
	cleanProject := strings.ToLower(strings.TrimSpace(projectID))
	cleanName := strings.ToLower(strings.TrimSpace(name))

	if cleanTenant == "" {
		return nil, errors.New("tenant id cannot be empty")
	}
	if cleanProject == "" {
		return nil, errors.New("project id cannot be empty")
	}
	if cleanName == "" {
		cleanName = string(envType)
	}

	if envType != EnvTypeDev && envType != EnvTypeStaging && envType != EnvTypeProd {
		return nil, fmt.Errorf("invalid environment type: %s (must be dev, staging, or prod)", envType)
	}

	id := fmt.Sprintf("%s-%s-%s", cleanTenant, cleanProject, envType)
	namespace := fmt.Sprintf("drr-tnt-%s-%s-%s", cleanTenant, cleanProject, envType)

	res := DefaultEnvResources(envType)
	if resources != nil {
		res = *resources
	}

	now := time.Now().UTC()
	return &Environment{
		ID:         id,
		TenantID:   cleanTenant,
		ProjectID:  cleanProject,
		Name:       cleanName,
		Type:       envType,
		Namespace:  namespace,
		Status:     EnvStatusPending,
		Resources:  res,
		Components: make([]*Component, 0),
		Labels:     labels,
		CreatedAt:  now,
		UpdatedAt:  now,
	}, nil
}

func (e *Environment) MarkProvisioned() {
	e.Status = EnvStatusProvisioned
	e.UpdatedAt = time.Now().UTC()
}

func (e *Environment) MarkActive() {
	e.Status = EnvStatusActive
	e.UpdatedAt = time.Now().UTC()
}

func (e *Environment) MarkDeploying() {
	e.Status = EnvStatusDeploying
	e.UpdatedAt = time.Now().UTC()
}

func (e *Environment) AddComponent(c *Component) {
	e.Components = append(e.Components, c)
	e.UpdatedAt = time.Now().UTC()
}
