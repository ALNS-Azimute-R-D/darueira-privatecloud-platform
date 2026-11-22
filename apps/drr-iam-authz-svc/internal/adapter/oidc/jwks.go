package oidc

import (
	"context"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"sync"
	"time"
)

// jwksCache holds the RSA signing keys of the realm, fetched from the JWKS endpoint.
//
// Keys are cached for ttl. An unknown "kid" (key rotation) triggers a refresh, at most once per minRefresh, so a flood of tokens
// with random kids cannot turn this service into a load generator against Keycloak.
type jwksCache struct {
	url        string
	client     *http.Client
	ttl        time.Duration
	minRefresh time.Duration

	mu          sync.Mutex
	keys        map[string]*rsa.PublicKey
	fetchedAt   time.Time
	lastAttempt time.Time
}

func newJWKSCache(url string) *jwksCache {
	return &jwksCache{url: url, client: &http.Client{Timeout: 5 * time.Second}, ttl: 10 * time.Minute, minRefresh: 10 * time.Second}
}

// key returns the public key for kid, refreshing the set when it is stale or the kid is unknown.
func (c *jwksCache) key(ctx context.Context, kid string) (*rsa.PublicKey, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	fresh := time.Since(c.fetchedAt) < c.ttl
	if k, ok := c.keys[kid]; ok && fresh {
		return k, nil
	}
	if time.Since(c.lastAttempt) >= c.minRefresh {
		c.lastAttempt = time.Now()
		if err := c.refresh(ctx); err != nil {
			// Keep serving a known key if the refresh failed (Keycloak restarting) but never an unknown one.
			if k, ok := c.keys[kid]; ok {
				return k, nil
			}
			return nil, fmt.Errorf("cannot load the signing keys: %w", err)
		}
	}
	if k, ok := c.keys[kid]; ok {
		return k, nil
	}
	return nil, errors.New("unknown signing key")
}

type jwk struct {
	Kty string `json:"kty"`
	Kid string `json:"kid"`
	Use string `json:"use"`
	Alg string `json:"alg"`
	N   string `json:"n"`
	E   string `json:"e"`
}

func (c *jwksCache) refresh(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.url, nil)
	if err != nil {
		return err
	}
	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("JWKS endpoint answered HTTP %d", resp.StatusCode)
	}
	var doc struct {
		Keys []jwk `json:"keys"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&doc); err != nil {
		return fmt.Errorf("invalid JWKS document: %w", err)
	}
	keys := make(map[string]*rsa.PublicKey)
	for _, k := range doc.Keys {
		// Only RSA signature keys usable with RS256: skip encryption keys and anything else.
		if k.Kty != "RSA" || k.Kid == "" || (k.Use != "" && k.Use != "sig") || (k.Alg != "" && k.Alg != "RS256") {
			continue
		}
		pub, err := k.publicKey()
		if err != nil {
			continue
		}
		keys[k.Kid] = pub
	}
	if len(keys) == 0 {
		return errors.New("the JWKS document has no usable RS256 key")
	}
	c.keys, c.fetchedAt = keys, time.Now()
	return nil
}

func (k jwk) publicKey() (*rsa.PublicKey, error) {
	nb, err := base64.RawURLEncoding.DecodeString(k.N)
	if err != nil {
		return nil, err
	}
	eb, err := base64.RawURLEncoding.DecodeString(k.E)
	if err != nil {
		return nil, err
	}
	e := new(big.Int).SetBytes(eb)
	if !e.IsInt64() || e.Int64() < 3 || e.Int64() > 1<<31-1 {
		return nil, errors.New("invalid RSA exponent")
	}
	n := new(big.Int).SetBytes(nb)
	if n.BitLen() < 2048 {
		return nil, errors.New("RSA key shorter than 2048 bits")
	}
	return &rsa.PublicKey{N: n, E: int(e.Int64())}, nil
}
