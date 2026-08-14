package http

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/service"
)

type Router struct {
	orchSvc *service.OrchestratorService
	mux     *http.ServeMux
}

func NewRouter(orchSvc *service.OrchestratorService) *Router {
	r := &Router{
		orchSvc: orchSvc,
		mux:     http.NewServeMux(),
	}
	r.registerRoutes()
	return r
}

func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	r.mux.ServeHTTP(w, req)
}

func (r *Router) registerRoutes() {
	r.mux.HandleFunc("/healthz", r.handleHealth)
	r.mux.HandleFunc("/readyz", r.handleHealth)
	r.mux.HandleFunc("/api/v1/environments", r.handleEnvironments)
	r.mux.HandleFunc("/api/v1/environments/", r.handleEnvironmentResource)
}

func (r *Router) handleHealth(w http.ResponseWriter, req *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "healthy",
		"service": "drr-env-orchestrator-svc",
		"tier":    "enterprise-shared",
	})
}

func (r *Router) handleEnvironments(w http.ResponseWriter, req *http.Request) {
	ctx := req.Context()
	switch req.Method {
	case http.MethodGet:
		tenantID := req.URL.Query().Get("tenantId")
		projectID := req.URL.Query().Get("projectId")
		envs, err := r.orchSvc.ListEnvironments(ctx, tenantID, projectID)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		writeJSON(w, http.StatusOK, envs)

	case http.MethodPost:
		var input service.CreateEnvironmentInput
		if err := json.NewDecoder(req.Body).Decode(&input); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		env, err := r.orchSvc.CreateEnvironment(ctx, input)
		if err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
		writeJSON(w, http.StatusCreated, env)

	default:
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

func (r *Router) handleEnvironmentResource(w http.ResponseWriter, req *http.Request) {
	path := strings.TrimPrefix(req.URL.Path, "/api/v1/environments/")
	segments := strings.Split(strings.Trim(path, "/"), "/")

	if len(segments) == 0 || segments[0] == "" {
		writeError(w, http.StatusNotFound, "resource not found")
		return
	}

	envID := segments[0]
	ctx := req.Context()

	// 1. /api/v1/environments/{id}
	if len(segments) == 1 {
		switch req.Method {
		case http.MethodGet:
			env, err := r.orchSvc.GetEnvironment(ctx, envID)
			if err != nil {
				writeError(w, http.StatusNotFound, err.Error())
				return
			}
			writeJSON(w, http.StatusOK, env)

		case http.MethodDelete:
			if err := r.orchSvc.DeleteEnvironment(ctx, envID); err != nil {
				writeError(w, http.StatusNotFound, err.Error())
				return
			}
			writeJSON(w, http.StatusOK, map[string]string{"message": "environment deleted successfully"})

		default:
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		}
		return
	}

	// 2. /api/v1/environments/{id}/deploy
	if len(segments) == 2 && segments[1] == "deploy" && req.Method == http.MethodPost {
		var input service.DeployEnvironmentInput
		if err := json.NewDecoder(req.Body).Decode(&input); err != nil {
			// Allow empty body with default deployment
			input = service.DeployEnvironmentInput{}
		}
		input.EnvID = envID
		result, err := r.orchSvc.DeployEnvironment(ctx, input)
		if err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
		writeJSON(w, http.StatusOK, result)
		return
	}

	writeError(w, http.StatusNotFound, "resource not found")
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}
