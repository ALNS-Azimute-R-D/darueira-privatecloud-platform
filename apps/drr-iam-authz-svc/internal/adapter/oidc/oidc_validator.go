package oidc

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/domain"
	"github.com/golang-jwt/jwt/v5"
)

type OIDCValidator struct {
	issuerURL string
	secretKey []byte
}

func NewOIDCValidator(issuerURL string, secretKey string) *OIDCValidator {
	return &OIDCValidator{
		issuerURL: issuerURL,
		secretKey: []byte(secretKey),
	}
}

type CustomClaims struct {
	Email             string   `json:"email"`
	PreferredUsername string   `json:"preferred_username"`
	TenantID          string   `json:"tenant_id"`
	Roles             []string `json:"roles"`
	Groups            []string `json:"groups"`
	jwt.RegisteredClaims
}

func (v *OIDCValidator) ValidateToken(ctx context.Context, tokenString string) (*domain.TokenClaims, error) {
	if tokenString == "" {
		return nil, errors.New("empty token string")
	}

	// Parse token without signature verification if no secret is configured (dev/mock mode)
	if len(v.secretKey) == 0 {
		parser := jwt.NewParser()
		token, _, err := parser.ParseUnverified(tokenString, &CustomClaims{})
		if err != nil {
			return nil, fmt.Errorf("failed to parse unverified token: %w", err)
		}

		if claims, ok := token.Claims.(*CustomClaims); ok {
			return mapToDomainClaims(claims), nil
		}
		return nil, errors.New("invalid claims format")
	}

	// Parse with HMAC validation
	token, err := jwt.ParseWithClaims(tokenString, &CustomClaims{}, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return v.secretKey, nil
	})

	if err != nil {
		return nil, fmt.Errorf("token validation failed: %w", err)
	}

	if claims, ok := token.Claims.(*CustomClaims); ok && token.Valid {
		if claims.ExpiresAt != nil && claims.ExpiresAt.Before(time.Now()) {
			return nil, errors.New("token is expired")
		}
		return mapToDomainClaims(claims), nil
	}

	return nil, errors.New("invalid token claims")
}

func mapToDomainClaims(c *CustomClaims) *domain.TokenClaims {
	var iat, exp int64
	if c.IssuedAt != nil {
		iat = c.IssuedAt.Unix()
	}
	if c.ExpiresAt != nil {
		exp = c.ExpiresAt.Unix()
	}

	return &domain.TokenClaims{
		Subject:   c.Subject,
		Email:     c.Email,
		Preferred: c.PreferredUsername,
		TenantID:  c.TenantID,
		Roles:     c.Roles,
		Groups:    c.Groups,
		IssuedAt:  iat,
		ExpiresAt: exp,
	}
}
