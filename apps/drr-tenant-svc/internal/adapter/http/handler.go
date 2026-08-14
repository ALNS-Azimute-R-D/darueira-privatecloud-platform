package http

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/service"
)

type Router struct {
	tenantSvc  *service.TenantService
	projectSvc *service.ProjectService
	memberSvc  *service.MemberService
	mux        *http.ServeMux
}

func NewRouter(tenantSvc *service.TenantService, projectSvc *service.ProjectService, memberSvc *service.MemberService) *Router {
	r := &Router{
		tenantSvc:  tenantSvc,
		projectSvc: projectSvc,
		memberSvc:  memberSvc,
		mux:        http.NewServeMux(),
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
	r.mux.HandleFunc("/api/v1/tenants", r.handleTenants)
	r.mux.HandleFunc("/api/v1/tenants/", r.handleTenantResource)
}

func (r *Router) handleHealth(w http.ResponseWriter, req *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "healthy",
		"service": "drr-tenant-svc",
		"tier":    "enterprise-shared",
	})
}

func (r *Router) handleTenants(w http.ResponseWriter, req *http.Request) {
	ctx := req.Context()
	switch req.Method {
	case http.MethodGet:
		tenants, err := r.tenantSvc.ListTenants(ctx)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		writeJSON(w, http.StatusOK, tenants)

	case http.MethodPost:
		var input service.CreateTenantInput
		if err := json.NewDecoder(req.Body).Decode(&input); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
		tenant, err := r.tenantSvc.CreateTenant(ctx, input)
		if err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
		writeJSON(w, http.StatusCreated, tenant)

	default:
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

func (r *Router) handleTenantResource(w http.ResponseWriter, req *http.Request) {
	path := strings.TrimPrefix(req.URL.Path, "/api/v1/tenants/")
	segments := strings.Split(strings.Trim(path, "/"), "/")

	if len(segments) == 0 || segments[0] == "" {
		writeError(w, http.StatusNotFound, "resource not found")
		return
	}

	tenantID := segments[0]
	ctx := req.Context()

	// 1. /api/v1/tenants/{id}
	if len(segments) == 1 {
		switch req.Method {
		case http.MethodGet:
			tenant, err := r.tenantSvc.GetTenant(ctx, tenantID)
			if err != nil {
				writeError(w, http.StatusNotFound, err.Error())
				return
			}
			writeJSON(w, http.StatusOK, tenant)

		case http.MethodDelete:
			if err := r.tenantSvc.DeleteTenant(ctx, tenantID); err != nil {
				writeError(w, http.StatusNotFound, err.Error())
				return
			}
			writeJSON(w, http.StatusOK, map[string]string{"message": "tenant deleted successfully"})

		default:
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		}
		return
	}

	// Sub-resources: /api/v1/tenants/{id}/...
	subResource := segments[1]

	// 2. /api/v1/tenants/{id}/status
	if subResource == "status" && req.Method == http.MethodPatch {
		var body struct {
			Status domain.TenantStatus `json:"status"`
		}
		if err := json.NewDecoder(req.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid body")
			return
		}
		var tenant *domain.Tenant
		var err error
		if body.Status == domain.TenantStatusSuspended {
			tenant, err = r.tenantSvc.SuspendTenant(ctx, tenantID)
		} else if body.Status == domain.TenantStatusActive {
			tenant, err = r.tenantSvc.ActivateTenant(ctx, tenantID)
		} else {
			writeError(w, http.StatusBadRequest, "unsupported status transition")
			return
		}
		if err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
		writeJSON(w, http.StatusOK, tenant)
		return
	}

	// 3. /api/v1/tenants/{id}/quotas
	if subResource == "quotas" {
		switch req.Method {
		case http.MethodGet:
			tenant, err := r.tenantSvc.GetTenant(ctx, tenantID)
			if err != nil {
				writeError(w, http.StatusNotFound, err.Error())
				return
			}
			writeJSON(w, http.StatusOK, tenant.Quotas)

		case http.MethodPut:
			var quotas domain.ResourceQuotas
			if err := json.NewDecoder(req.Body).Decode(&quotas); err != nil {
				writeError(w, http.StatusBadRequest, "invalid quotas body")
				return
			}
			tenant, err := r.tenantSvc.UpdateQuotas(ctx, tenantID, quotas)
			if err != nil {
				writeError(w, http.StatusBadRequest, err.Error())
				return
			}
			writeJSON(w, http.StatusOK, tenant.Quotas)

		default:
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		}
		return
	}

	// 4. /api/v1/tenants/{id}/projects[/{projectId}]
	if subResource == "projects" {
		if len(segments) == 2 {
			switch req.Method {
			case http.MethodGet:
				projects, err := r.projectSvc.ListProjects(ctx, tenantID)
				if err != nil {
					writeError(w, http.StatusInternalServerError, err.Error())
					return
				}
				writeJSON(w, http.StatusOK, projects)

			case http.MethodPost:
				var input service.CreateProjectInput
				if err := json.NewDecoder(req.Body).Decode(&input); err != nil {
					writeError(w, http.StatusBadRequest, "invalid project body")
					return
				}
				input.TenantID = tenantID
				project, err := r.projectSvc.CreateProject(ctx, input)
				if err != nil {
					writeError(w, http.StatusBadRequest, err.Error())
					return
				}
				writeJSON(w, http.StatusCreated, project)

			default:
				writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			}
			return
		} else if len(segments) == 3 {
			projectID := segments[2]
			switch req.Method {
			case http.MethodGet:
				project, err := r.projectSvc.GetProject(ctx, tenantID, projectID)
				if err != nil {
					writeError(w, http.StatusNotFound, err.Error())
					return
				}
				writeJSON(w, http.StatusOK, project)

			case http.MethodDelete:
				if err := r.projectSvc.DeleteProject(ctx, tenantID, projectID); err != nil {
					writeError(w, http.StatusNotFound, err.Error())
					return
				}
				writeJSON(w, http.StatusOK, map[string]string{"message": "project deleted successfully"})

			default:
				writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			}
			return
		}
	}

	// 5. /api/v1/tenants/{id}/members[/{userId}]
	if subResource == "members" {
		if len(segments) == 2 {
			switch req.Method {
			case http.MethodGet:
				members, err := r.memberSvc.ListMembers(ctx, tenantID)
				if err != nil {
					writeError(w, http.StatusInternalServerError, err.Error())
					return
				}
				writeJSON(w, http.StatusOK, members)

			case http.MethodPost:
				var input service.AddMemberInput
				if err := json.NewDecoder(req.Body).Decode(&input); err != nil {
					writeError(w, http.StatusBadRequest, "invalid member body")
					return
				}
				input.TenantID = tenantID
				member, err := r.memberSvc.AddMember(ctx, input)
				if err != nil {
					writeError(w, http.StatusBadRequest, err.Error())
					return
				}
				writeJSON(w, http.StatusCreated, member)

			default:
				writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			}
			return
		} else if len(segments) == 3 {
			userID := segments[2]
			if req.Method == http.MethodDelete {
				if err := r.memberSvc.RemoveMember(ctx, tenantID, userID); err != nil {
					writeError(w, http.StatusNotFound, err.Error())
					return
				}
				writeJSON(w, http.StatusOK, map[string]string{"message": "member removed successfully"})
				return
			}
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
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
