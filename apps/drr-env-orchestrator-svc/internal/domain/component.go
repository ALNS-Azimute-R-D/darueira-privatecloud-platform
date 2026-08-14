package domain

import (
	"errors"
	"strings"
	"time"
)

type Component struct {
	Name      string            `json:"name"`
	Image     string            `json:"image"`
	Port      int               `json:"port"`
	Replicas  int32             `json:"replicas"`
	EnvVars   map[string]string `json:"envVars,omitempty"`
	CreatedAt time.Time         `json:"createdAt"`
}

func NewComponent(name, image string, port int, replicas int32, envVars map[string]string) (*Component, error) {
	cleanName := strings.ToLower(strings.TrimSpace(name))
	cleanImage := strings.TrimSpace(image)

	if cleanName == "" {
		return nil, errors.New("component name cannot be empty")
	}
	if cleanImage == "" {
		return nil, errors.New("component image cannot be empty")
	}
	if port <= 0 || port > 65535 {
		port = 8080
	}
	if replicas <= 0 {
		replicas = 1
	}

	return &Component{
		Name:      cleanName,
		Image:     cleanImage,
		Port:      port,
		Replicas:  replicas,
		EnvVars:   envVars,
		CreatedAt: time.Now().UTC(),
	}, nil
}
