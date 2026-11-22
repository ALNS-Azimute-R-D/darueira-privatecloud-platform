package oidc_test

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"math/big"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/adapter/oidc"
)

const issuer = "https://keycloak.test/realms/darueira"

type idp struct {
	t       *testing.T
	mu      sync.Mutex
	keys    map[string]*rsa.PrivateKey
	fetches atomic.Int32
	srv     *httptest.Server
}

func newIDP(t *testing.T) *idp {
	i := &idp{t: t, keys: map[string]*rsa.PrivateKey{}}
	i.addKey("kid-1")
	i.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		i.fetches.Add(1)
		i.mu.Lock()
		defer i.mu.Unlock()
		var keys []map[string]string
		for kid, k := range i.keys {
			keys = append(keys, map[string]string{"kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256",
				"n": base64.RawURLEncoding.EncodeToString(k.N.Bytes()), "e": base64.RawURLEncoding.EncodeToString(big.NewInt(int64(k.E)).Bytes())})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"keys": keys})
	}))
	t.Cleanup(i.srv.Close)
	return i
}

func (i *idp) addKey(kid string) {
	k, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		i.t.Fatal(err)
	}
	i.mu.Lock()
	i.keys[kid] = k
	i.mu.Unlock()
}

func (i *idp) sign(kid string, claims jwt.MapClaims) string {
	i.t.Helper()
	tok := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	tok.Header["kid"] = kid
	s, err := tok.SignedString(i.keys[kid])
	if err != nil {
		i.t.Fatal(err)
	}
	return s
}

func good() jwt.MapClaims {
	return jwt.MapClaims{"iss": issuer, "sub": "1111-2222", "email": "andre@darueira.local", "tenant": "darueira-corp",
		"iat": time.Now().Unix(), "exp": time.Now().Add(5 * time.Minute).Unix()}
}

func validator(i *idp) *oidc.OIDCValidator {
	return oidc.NewOIDCValidator(oidc.Options{Issuer: issuer, JWKSURL: i.srv.URL})
}

func TestValidTokenAndTenantClaim(t *testing.T) {
	i := newIDP(t)
	c, err := validator(i).ValidateToken(context.Background(), i.sign("kid-1", good()))
	if err != nil {
		t.Fatalf("valid token rejected: %v", err)
	}
	if c.Subject != "1111-2222" || c.TenantID != "darueira-corp" {
		t.Errorf("unexpected claims: %+v", c)
	}
}

func TestTenantClaimVariants(t *testing.T) {
	i := newIDP(t)
	v := validator(i)
	for name, tc := range map[string]struct {
		mod  func(jwt.MapClaims)
		want string
	}{
		"tenant_id wins":          {func(c jwt.MapClaims) { c["tenant_id"] = "acme" }, "acme"},
		"one-element list":        {func(c jwt.MapClaims) { c["tenant"] = []string{"swfabrik-europe"} }, "swfabrik-europe"},
		"two tenants are ignored": {func(c jwt.MapClaims) { c["tenant"] = []string{"a", "b"} }, ""},
		"missing":                 {func(c jwt.MapClaims) { delete(c, "tenant") }, ""},
	} {
		cl := good()
		tc.mod(cl)
		got, err := v.ValidateToken(context.Background(), i.sign("kid-1", cl))
		if err != nil || got.TenantID != tc.want {
			t.Errorf("%s: tenant=%q err=%v, want %q", name, got.TenantID, err, tc.want)
		}
	}
}

func TestRejectedTokens(t *testing.T) {
	i := newIDP(t)
	v := validator(i)
	other, _ := rsa.GenerateKey(rand.Reader, 2048)

	forged := jwt.NewWithClaims(jwt.SigningMethodRS256, good())
	forged.Header["kid"] = "kid-1"
	forgedStr, _ := forged.SignedString(other) // right kid, wrong private key

	none, _ := jwt.NewWithClaims(jwt.SigningMethodNone, good()).SignedString(jwt.UnsafeAllowNoneSignatureType)
	hs := jwt.NewWithClaims(jwt.SigningMethodHS256, good())
	hs.Header["kid"] = "kid-1"
	hsStr, _ := hs.SignedString([]byte("anything"))

	expired := good()
	expired["exp"] = time.Now().Add(-10 * time.Minute).Unix()
	noExp := good()
	delete(noExp, "exp")
	badIss := good()
	badIss["iss"] = "https://evil.test/realms/darueira"
	noSub := good()
	delete(noSub, "sub")

	for name, tok := range map[string]string{
		"signed with another key": forgedStr,
		"alg none":                none,
		"HS256":                   hsStr,
		"expired":                 i.sign("kid-1", expired),
		"no exp":                  i.sign("kid-1", noExp),
		"wrong issuer":            i.sign("kid-1", badIss),
		"no subject":              i.sign("kid-1", noSub),
		"garbage":                 "not-a-jwt",
		"empty":                   "",
	} {
		if _, err := v.ValidateToken(context.Background(), tok); err == nil {
			t.Errorf("%s: token was accepted", name)
		}
	}
}

func TestUnknownKidAndKeyRotation(t *testing.T) {
	i := newIDP(t)
	v := validator(i)
	if _, err := v.ValidateToken(context.Background(), i.sign("kid-1", good())); err != nil {
		t.Fatalf("kid-1: %v", err)
	}
	i.addKey("kid-2") // rotated in after the validator cached the set
	// A refresh is rate limited (10 s): kid-2 is rejected inside the window, never accepted unverified.
	if _, err := v.ValidateToken(context.Background(), i.sign("kid-2", good())); err == nil {
		t.Error("an unknown kid within the refresh window must be rejected")
	}
	// Once the window has passed, the new key is picked up and the token is accepted; kid-1 keeps working.
	v.SetRefreshWindow(0)
	if _, err := v.ValidateToken(context.Background(), i.sign("kid-2", good())); err != nil {
		t.Errorf("kid-2 after the refresh window: %v", err)
	}
	if _, err := v.ValidateToken(context.Background(), i.sign("kid-1", good())); err != nil {
		t.Errorf("kid-1 after rotation: %v", err)
	}
}

func TestRandomKidsDoNotHammerTheIDP(t *testing.T) {
	i := newIDP(t)
	v := validator(i)
	other, _ := rsa.GenerateKey(rand.Reader, 2048)
	for n := 0; n < 50; n++ {
		tok := jwt.NewWithClaims(jwt.SigningMethodRS256, good())
		tok.Header["kid"] = "random-" + string(rune('a'+n%26))
		s, _ := tok.SignedString(other)
		_, _ = v.ValidateToken(context.Background(), s)
	}
	if f := i.fetches.Load(); f > 2 {
		t.Errorf("the JWKS endpoint was fetched %d times for 50 bad tokens, want at most 2", f)
	}
}

func TestNotConfiguredRejectsEverything(t *testing.T) {
	i := newIDP(t)
	for name, v := range map[string]*oidc.OIDCValidator{
		"no options":  oidc.NewOIDCValidator(oidc.Options{}),
		"no JWKS url": oidc.NewOIDCValidator(oidc.Options{Issuer: issuer}),
		"no issuer":   oidc.NewOIDCValidator(oidc.Options{JWKSURL: i.srv.URL}),
	} {
		if _, err := v.ValidateToken(context.Background(), i.sign("kid-1", good())); err == nil {
			t.Errorf("%s: a validator without configuration must reject every token (no dev/mock mode)", name)
		}
	}
}

func TestAudience(t *testing.T) {
	i := newIDP(t)
	v := oidc.NewOIDCValidator(oidc.Options{Issuer: issuer, JWKSURL: i.srv.URL, Audience: "darueira-api"})
	wrong := good()
	wrong["aud"] = "other"
	if _, err := v.ValidateToken(context.Background(), i.sign("kid-1", wrong)); err == nil {
		t.Error("wrong audience accepted")
	}
	right := good()
	right["aud"] = []string{"account", "darueira-api"}
	if _, err := v.ValidateToken(context.Background(), i.sign("kid-1", right)); err != nil {
		t.Errorf("right audience rejected: %v", err)
	}
}

func TestIDPDownRejectsEverything(t *testing.T) {
	i := newIDP(t)
	tok := i.sign("kid-1", good())
	down := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "down", http.StatusServiceUnavailable)
	}))
	defer down.Close()
	v := oidc.NewOIDCValidator(oidc.Options{Issuer: issuer, JWKSURL: down.URL})
	if _, err := v.ValidateToken(context.Background(), tok); err == nil {
		t.Error("with the identity provider down the token must be rejected (fail closed)")
	}
}
