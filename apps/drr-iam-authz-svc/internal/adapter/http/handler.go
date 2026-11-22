package http

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/domain"
)

// DecisionObserver receives the outcome ("allowed", "denied", "error") of every authorization decision, by endpoint.
type DecisionObserver func(endpoint, decision string)

// Option customizes an AuthzHandler.
type Option func(*AuthzHandler)

// WithDecisionObserver registers a callback for authorization outcomes (used to export metrics).
func WithDecisionObserver(o DecisionObserver) Option {
	return func(h *AuthzHandler) { h.observe = o }
}

type AuthzHandler struct {
	authzService domain.AuthzServicePort
	observe      DecisionObserver
}

func NewAuthzHandler(authzService domain.AuthzServicePort, opts ...Option) *AuthzHandler {
	h := &AuthzHandler{
		authzService: authzService,
		observe:      func(string, string) {},
	}
	for _, opt := range opts {
		opt(h)
	}
	return h
}

func (h *AuthzHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /healthz", h.HandleHealthz)
	mux.HandleFunc("GET /readyz", h.HandleReadyz)
	mux.HandleFunc("POST /api/v1/authz/check", h.HandleCheck)
	mux.HandleFunc("POST /api/v1/authz/batch-check", h.HandleBatchCheck)
	mux.HandleFunc("POST /api/v1/authz/tuples", h.HandleTupleMutation)
	mux.HandleFunc("DELETE /api/v1/authz/tuples", h.HandleTupleMutation)
	mux.HandleFunc("GET /api/v1/authz/forward-auth", h.HandleForwardAuth)
}

func (h *AuthzHandler) HandleHealthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "UP", "service": "drr-iam-authz-svc"})
}

func (h *AuthzHandler) HandleReadyz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "READY", "service": "drr-iam-authz-svc"})
}

func (h *AuthzHandler) HandleCheck(w http.ResponseWriter, r *http.Request) {
	var req domain.PermissionCheckRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid JSON request body"}`, http.StatusBadRequest)
		return
	}

	resp, err := h.authzService.CheckPermission(r.Context(), req)
	if err != nil {
		h.observe("check", "error")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	h.observe("check", decisionOf(resp.Allowed))
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(resp)
}

func decisionOf(allowed bool) string {
	if allowed {
		return "allowed"
	}
	return "denied"
}

func (h *AuthzHandler) HandleBatchCheck(w http.ResponseWriter, r *http.Request) {
	var req domain.BatchCheckRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid JSON request body"}`, http.StatusBadRequest)
		return
	}

	resp, err := h.authzService.BatchCheckPermission(r.Context(), req)
	if err != nil {
		h.observe("batch_check", "error")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	for _, result := range resp.Results {
		h.observe("batch_check", decisionOf(result.Allowed))
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(resp)
}

func (h *AuthzHandler) HandleTupleMutation(w http.ResponseWriter, r *http.Request) {
	var raw map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		http.Error(w, `{"error":"invalid JSON request body"}`, http.StatusBadRequest)
		return
	}

	var event domain.TupleMutationEvent
	if action, ok := raw["action"].(string); ok {
		event.Action = domain.MutationAction(action)
	} else {
		if r.Method == http.MethodDelete {
			event.Action = domain.ActionDelete
		} else {
			event.Action = domain.ActionInsert
		}
	}

	if tupleMap, ok := raw["tuple"].(map[string]interface{}); ok {
		if u, ok := tupleMap["user"].(string); ok {
			event.Tuple.User = u
		}
		if rel, ok := tupleMap["relation"].(string); ok {
			event.Tuple.Relation = rel
		}
		if obj, ok := tupleMap["object"].(string); ok {
			event.Tuple.Object = obj
		}
	} else {
		if u, ok := raw["user"].(string); ok {
			event.Tuple.User = u
		}
		if rel, ok := raw["relation"].(string); ok {
			event.Tuple.Relation = rel
		}
		if obj, ok := raw["object"].(string); ok {
			event.Tuple.Object = obj
		}
	}

	if err := h.authzService.HandleTupleMutation(r.Context(), event); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "applied"})
}

// HandleForwardAuth is the external auth verification hook for APISIX Ingress
func (h *AuthzHandler) HandleForwardAuth(w http.ResponseWriter, r *http.Request) {
	authHeader := r.Header.Get("Authorization")
	if authHeader == "" {
		h.observe("forward_auth", "error")
		http.Error(w, "Unauthorized: missing Authorization header", http.StatusUnauthorized)
		return
	}

	relation := r.URL.Query().Get("relation")
	object := r.URL.Query().Get("object")

	// Empty relation or object: the service checks membership of the tenant in the token (see ValidateAndCheck).
	resp, claims, err := h.authzService.ValidateAndCheck(r.Context(), authHeader, relation, object)
	if err != nil {
		h.observe("forward_auth", "error")
		http.Error(w, "Unauthorized: "+err.Error(), http.StatusUnauthorized)
		return
	}

	h.observe("forward_auth", decisionOf(resp.Allowed))
	if !resp.Allowed {
		http.Error(w, "Forbidden: permission denied by OpenFGA policy", http.StatusForbidden)
		return
	}

	// Inject authenticated identity context back to downstream proxies
	if claims != nil {
		w.Header().Set("X-Auth-Subject", claims.Subject)
		w.Header().Set("X-Auth-Email", claims.Email)
		w.Header().Set("X-Auth-Tenant", claims.TenantID)
		if len(claims.Roles) > 0 {
			w.Header().Set("X-Auth-Roles", strings.Join(claims.Roles, ","))
		}
	}

	w.WriteHeader(http.StatusOK)
}
