// Package oidc validates the bearer tokens presented to drr-iam-authz-svc (ADR-0022).
package oidc

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/domain"
)

// Options configures the validator. Issuer and JWKSURL are mandatory: without them every token is rejected (fail closed).
type Options struct {
	Issuer   string // exact value of the "iss" claim (the public URL of the realm)
	JWKSURL  string // where the realm signing keys are fetched from (in-cluster URL)
	Audience string // optional: required "aud" value
}

// OIDCValidator verifies RS256 tokens signed by the realm of the identity provider.
type OIDCValidator struct {
	parser *jwt.Parser
	keys   *jwksCache
	err    error
}

// NewOIDCValidator never panics and never accepts unverified tokens: a bad configuration yields a validator that rejects everything.
func NewOIDCValidator(o Options) *OIDCValidator {
	if o.Issuer == "" || o.JWKSURL == "" {
		return &OIDCValidator{err: errors.New("token validation is not configured (OIDC_ISSUER_URL and OIDC_JWKS_URL are required)")}
	}
	opts := []jwt.ParserOption{
		jwt.WithValidMethods([]string{"RS256"}), // no HMAC, no "none"
		jwt.WithIssuer(o.Issuer),
		jwt.WithExpirationRequired(),
		jwt.WithLeeway(30 * time.Second),
	}
	if o.Audience != "" {
		opts = append(opts, jwt.WithAudience(o.Audience))
	}
	return &OIDCValidator{parser: jwt.NewParser(opts...), keys: newJWKSCache(o.JWKSURL)}
}

// CustomClaims are the claims the platform reads. Keycloak emits the tenant as "tenant" (user attribute); "tenant_id" is also accepted.
type CustomClaims struct {
	Email             string   `json:"email"`
	PreferredUsername string   `json:"preferred_username"`
	TenantID          string   `json:"tenant_id"`
	Tenant            any      `json:"tenant"`
	Roles             []string `json:"roles"`
	Groups            []string `json:"groups"`
	jwt.RegisteredClaims
}

func (v *OIDCValidator) ValidateToken(ctx context.Context, tokenString string) (*domain.TokenClaims, error) {
	if v.err != nil {
		return nil, v.err
	}
	if tokenString == "" {
		return nil, errors.New("empty token string")
	}
	token, err := v.parser.ParseWithClaims(tokenString, &CustomClaims{}, func(t *jwt.Token) (interface{}, error) {
		kid, _ := t.Header["kid"].(string)
		if kid == "" {
			return nil, errors.New("token has no kid")
		}
		return v.keys.key(ctx, kid)
	})
	if err != nil {
		return nil, fmt.Errorf("token validation failed: %w", err)
	}
	claims, ok := token.Claims.(*CustomClaims)
	if !ok || !token.Valid {
		return nil, errors.New("invalid token claims")
	}
	if claims.Subject == "" {
		return nil, errors.New("token has no subject")
	}
	return mapToDomainClaims(claims), nil
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
		TenantID:  tenantOf(c),
		Roles:     c.Roles,
		Groups:    c.Groups,
		IssuedAt:  iat,
		ExpiresAt: exp,
	}
}

// tenantOf returns "tenant_id" if present, otherwise "tenant" (a string or a one-element list).
func tenantOf(c *CustomClaims) string {
	if c.TenantID != "" {
		return c.TenantID
	}
	switch t := c.Tenant.(type) {
	case string:
		return t
	case []any:
		if len(t) == 1 {
			if s, ok := t[0].(string); ok {
				return s
			}
		}
	}
	return ""
}
