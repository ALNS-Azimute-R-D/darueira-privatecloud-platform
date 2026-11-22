// Package metrics exposes the Prometheus metrics of drr-iam-authz-svc.
//
// The metrics are served by a dedicated listener (see Server), never by the public API port: the APISIX route of this
// service forwards every path of port 8080, so /metrics on that port would be published through the gateway.
package metrics

import (
	"net/http"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/collectors"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

const namespace = "drr_iam_authz"

// Decision outcomes of an authorization check.
const (
	DecisionAllowed = "allowed"
	DecisionDenied  = "denied"
	DecisionError   = "error"
)

// Metrics groups the collectors of the service.
type Metrics struct {
	registry  *prometheus.Registry
	requests  *prometheus.CounterVec
	duration  *prometheus.HistogramVec
	inFlight  prometheus.Gauge
	decisions *prometheus.CounterVec
}

// New creates the registry with the Go runtime and process collectors plus the service collectors.
func New(version string) *Metrics {
	reg := prometheus.NewRegistry()
	m := &Metrics{
		registry: reg,
		requests: prometheus.NewCounterVec(prometheus.CounterOpts{
			Namespace: namespace, Name: "http_requests_total",
			Help: "HTTP requests handled by the API, by method, route pattern and status code.",
		}, []string{"method", "route", "code"}),
		duration: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Namespace: namespace, Name: "http_request_duration_seconds",
			Help:    "HTTP request latency by method and route pattern.",
			Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
		}, []string{"method", "route"}),
		inFlight: prometheus.NewGauge(prometheus.GaugeOpts{
			Namespace: namespace, Name: "http_requests_in_flight", Help: "HTTP requests being served right now.",
		}),
		decisions: prometheus.NewCounterVec(prometheus.CounterOpts{
			Namespace: namespace, Name: "decisions_total",
			Help: "Authorization decisions by endpoint (check, batch_check, forward_auth) and outcome (allowed, denied, error).",
		}, []string{"endpoint", "decision"}),
	}
	build := prometheus.NewGauge(prometheus.GaugeOpts{
		Namespace: namespace, Name: "build_info", Help: "Build information; the value is always 1.",
		ConstLabels: prometheus.Labels{"version": version},
	})
	build.Set(1)
	reg.MustRegister(collectors.NewGoCollector(), collectors.NewProcessCollector(collectors.ProcessCollectorOpts{}),
		m.requests, m.duration, m.inFlight, m.decisions, build)
	// Create the series at 0 so that rate() and alerts work before the first request.
	for _, e := range []string{"check", "batch_check", "forward_auth"} {
		for _, d := range []string{DecisionAllowed, DecisionDenied, DecisionError} {
			m.decisions.WithLabelValues(e, d)
		}
	}
	return m
}

// ObserveDecision records one authorization outcome. It matches the decision observer option of the HTTP handler.
func (m *Metrics) ObserveDecision(endpoint, decision string) {
	m.decisions.WithLabelValues(endpoint, decision).Inc()
}

// Middleware instruments the API. The route label is the ServeMux pattern (for example "POST /api/v1/authz/check"),
// never the raw path, so the number of series stays bounded; unmatched requests share the label "unmatched".
func (m *Metrics) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		m.inFlight.Inc()
		defer m.inFlight.Dec()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(rec, r)
		route := r.Pattern // filled in by ServeMux (Go 1.23+) on the request that reaches the handler
		if route == "" {
			route = "unmatched"
		}
		m.requests.WithLabelValues(r.Method, route, strconv.Itoa(rec.status)).Inc()
		m.duration.WithLabelValues(r.Method, route).Observe(time.Since(start).Seconds())
	})
}

// Handler serves the registry in the Prometheus text format.
func (m *Metrics) Handler() http.Handler {
	return promhttp.HandlerFor(m.registry, promhttp.HandlerOpts{Registry: m.registry})
}

// Server returns the HTTP server of the metrics listener: only GET /metrics, on its own port.
func (m *Metrics) Server(port string) *http.Server {
	mux := http.NewServeMux()
	mux.Handle("GET /metrics", m.Handler())
	return &http.Server{Addr: ":" + port, Handler: mux, ReadHeaderTimeout: 5 * time.Second, WriteTimeout: 10 * time.Second}
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (s *statusRecorder) WriteHeader(code int) {
	s.status = code
	s.ResponseWriter.WriteHeader(code)
}
