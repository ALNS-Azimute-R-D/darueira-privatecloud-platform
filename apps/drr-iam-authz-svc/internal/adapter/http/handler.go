package http

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/domain"
)

type AuthzHandler struct {
	authzService domain.AuthzServicePort
}

func NewAuthzHandler(authzService domain.AuthzServicePort) *AuthzHandler {
	return &AuthzHandler{
		authzService: authzService,
	}
}

func (h *AuthzHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /healthz", h.HandleHealthz)
	mux.HandleFunc("GET /readyz", h.HandleReadyz)
	mux.HandleFunc("POST /api/v1/authz/check", h.HandleCheck)
	mux.HandleFunc("POST /api/v1/authz/batch-check", h.HandleBatchCheck)
	mux.HandleFunc("POST /api/v1/authz/tuples", h.HandleTupleMutation)
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
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(resp)
}

func (h *AuthzHandler) HandleBatchCheck(w http.ResponseWriter, r *http.Request) {
	var req domain.BatchCheckRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid JSON request body"}`, http.StatusBadRequest)
		return
	}

	resp, err := h.authzService.BatchCheckPermission(r.Context(), req)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(resp)
}

func (h *AuthzHandler) HandleTupleMutation(w http.ResponseWriter, r *http.Request) {
	var event domain.TupleMutationEvent
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		http.Error(w, `{"error":"invalid JSON request body"}`, http.StatusBadRequest)
		return
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
		http.Error(w, "Unauthorized: missing Authorization header", http.StatusUnauthorized)
		return
	}

	relation := r.URL.Query().Get("relation")
	object := r.URL.Query().Get("object")

	if relation == "" || object == "" {
		// Default to read/viewer check if not explicitly provided
		relation = "viewer"
		object = "tenant:default"
	}

	resp, claims, err := h.authzService.ValidateAndCheck(r.Context(), authHeader, relation, object)
	if err != nil {
		http.Error(w, "Unauthorized: "+err.Error(), http.StatusUnauthorized)
		return
	}

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
