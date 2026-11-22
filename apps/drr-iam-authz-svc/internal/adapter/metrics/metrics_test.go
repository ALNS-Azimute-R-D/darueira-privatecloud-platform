package metrics_test

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/adapter/metrics"
)

func scrape(t *testing.T, m *metrics.Metrics) string {
	t.Helper()
	rr := httptest.NewRecorder()
	m.Handler().ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	if rr.Code != http.StatusOK {
		t.Fatalf("metrics status = %d", rr.Code)
	}
	b, _ := io.ReadAll(rr.Body)
	return string(b)
}

func TestMiddlewareLabelsByRoutePatternNotRawPath(t *testing.T) {
	m := metrics.New("test")
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	mux.HandleFunc("POST /api/v1/authz/check", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusForbidden) })
	h := m.Middleware(mux)

	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodGet, "/healthz", nil))
	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodPost, "/api/v1/authz/check", nil))
	h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodGet, "/random/user-123/path", nil))

	out := scrape(t, m)
	for _, want := range []string{
		`drr_iam_authz_http_requests_total{code="200",method="GET",route="GET /healthz"} 1`,
		`drr_iam_authz_http_requests_total{code="403",method="POST",route="POST /api/v1/authz/check"} 1`,
		`drr_iam_authz_http_requests_total{code="404",method="GET",route="unmatched"} 1`,
		`drr_iam_authz_http_request_duration_seconds_count{method="GET",route="GET /healthz"} 1`,
	} {
		if !strings.Contains(out, want) {
			t.Errorf("missing series %q in:\n%s", want, out)
		}
	}
	if strings.Contains(out, "user-123") {
		t.Error("raw request path leaked into a label (unbounded cardinality)")
	}
}

func TestDecisionsStartAtZeroAndCount(t *testing.T) {
	m := metrics.New("test")
	if out := scrape(t, m); !strings.Contains(out, `drr_iam_authz_decisions_total{decision="denied",endpoint="forward_auth"} 0`) {
		t.Errorf("decision series should exist at 0:\n%s", out)
	}
	m.ObserveDecision("check", metrics.DecisionAllowed)
	m.ObserveDecision("check", metrics.DecisionAllowed)
	if out := scrape(t, m); !strings.Contains(out, `drr_iam_authz_decisions_total{decision="allowed",endpoint="check"} 2`) {
		t.Errorf("allowed counter should be 2:\n%s", out)
	}
}

func TestBuildInfoAndRuntimeMetricsArePresent(t *testing.T) {
	out := scrape(t, metrics.New("v9.9.9"))
	for _, want := range []string{`drr_iam_authz_build_info{version="v9.9.9"} 1`, "go_goroutines", "process_resident_memory_bytes"} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %q", want)
		}
	}
}

func TestMetricsServerExposesOnlyMetrics(t *testing.T) {
	srv := metrics.New("test").Server("0")
	for path, want := range map[string]int{"/metrics": http.StatusOK, "/api/v1/authz/check": http.StatusNotFound, "/healthz": http.StatusNotFound} {
		rr := httptest.NewRecorder()
		srv.Handler.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, path, nil))
		if rr.Code != want {
			t.Errorf("%s: status %d, want %d", path, rr.Code, want)
		}
	}
}
