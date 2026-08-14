package domain

import (
	"errors"
	"strings"
	"time"
)

type TenantRole string

const (
	TenantRoleAdmin  TenantRole = "admin"
	TenantRoleMember TenantRole = "member"
)

type TenantMember struct {
	TenantID  string     `json:"tenantId"`
	UserID    string     `json:"userId"`
	Role      TenantRole `json:"role"`
	CreatedAt time.Time  `json:"createdAt"`
}

func NewTenantMember(tenantID, userID string, role TenantRole) (*TenantMember, error) {
	cleanTenantID := strings.ToLower(strings.TrimSpace(tenantID))
	cleanUserID := strings.TrimSpace(userID)

	if cleanTenantID == "" {
		return nil, errors.New("tenant id cannot be empty")
	}
	if cleanUserID == "" {
		return nil, errors.New("user id cannot be empty")
	}
	if role != TenantRoleAdmin && role != TenantRoleMember {
		return nil, errors.New("invalid tenant role: must be 'admin' or 'member'")
	}

	return &TenantMember{
		TenantID:  cleanTenantID,
		UserID:    cleanUserID,
		Role:      role,
		CreatedAt: time.Now().UTC(),
	}, nil
}
