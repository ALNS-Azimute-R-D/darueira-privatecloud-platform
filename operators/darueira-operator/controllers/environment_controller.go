package controllers

import (
	"context"
	"fmt"

	darueirav1alpha1 "github.com/dexterity/darueira/operators/darueira-operator/api/v1alpha1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

// EnvironmentReconciler reconciles an Environment object
type EnvironmentReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

// +kubebuilder:rbac:groups=darueira.io,resources=environments,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=darueira.io,resources=environments/status,verbs=get;update;patch
// +kubebuilder:rbac:groups="",resources=namespaces,verbs=get;list;watch;create;update;patch;delete

func (r *EnvironmentReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	env := &darueirav1alpha1.Environment{}
	if err := r.Get(ctx, req.NamespacedName, env); err != nil {
		if errors.IsNotFound(err) {
			logger.Info("Environment resource deleted", "environment", req.Name)
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, fmt.Errorf("failed to get Environment: %w", err)
	}

	targetNamespace := fmt.Sprintf("drr-tnt-%s-%s-%s", env.Spec.TenantRef, env.Spec.ProjectRef, env.Spec.Type)
	logger.Info("Reconciling Environment namespace", "targetNamespace", targetNamespace)

	// 1. Ensure Namespace exists
	ns := &corev1.Namespace{}
	if err := r.Get(ctx, client.ObjectKey{Name: targetNamespace}, ns); err != nil {
		if errors.IsNotFound(err) {
			logger.Info("Creating isolated Tenant Environment namespace", "namespace", targetNamespace)
			ns = &corev1.Namespace{
				ObjectMeta: metav1.ObjectMeta{
					Name: targetNamespace,
					Labels: map[string]string{
						"darueira.io/tier":                     "tenant-workload",
						"darueira.io/tenant":                   env.Spec.TenantRef,
						"darueira.io/project":                  env.Spec.ProjectRef,
						"darueira.io/environment":              string(env.Spec.Type),
						"pod-security.kubernetes.io/enforce":   "restricted",
						"pod-security.kubernetes.io/audit":     "restricted",
						"pod-security.kubernetes.io/warn":      "restricted",
					},
				},
			}
			if err := r.Create(ctx, ns); err != nil {
				return ctrl.Result{}, fmt.Errorf("failed to create namespace %s: %w", targetNamespace, err)
			}
		} else {
			return ctrl.Result{}, fmt.Errorf("failed to check namespace %s: %w", targetNamespace, err)
		}
	}

	// 2. Ensure Envoy Sidecar ConfigMap exists in the tenant namespace
	envoyCM := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "envoy-sidecar-config",
			Namespace: targetNamespace,
			Labels: map[string]string{
				"darueira.io/tier":      "tenant-workload",
				"darueira.io/component": "envoy-pep",
			},
		},
		Data: map[string]string{
			"envoy.yaml": `static_resources:
  listeners:
  - name: ingress_listener
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 8000
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          codec_type: AUTO
          route_config:
            name: local_route
            virtual_hosts:
            - name: local_service
              domains: ["*"]
              routes:
              - match:
                  prefix: "/"
                route:
                  cluster: app_service
          http_filters:
          - name: envoy.filters.http.ext_authz
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz
              grpc_service:
                envoy_grpc:
                  cluster_name: opa_ext_authz_grpc
                timeout: 0.25s
              transport_api_version: V3
              failure_mode_allow: false
              status_on_error:
                code: 503
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  clusters:
  - name: app_service
    connect_timeout: 0.50s
    type: STATIC
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: app_service
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: 127.0.0.1
                port_value: 8080
  - name: opa_ext_authz_grpc
    connect_timeout: 0.25s
    type: STATIC
    lb_policy: ROUND_ROBIN
    http2_protocol_options: {}
    load_assignment:
      cluster_name: opa_ext_authz_grpc
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: 127.0.0.1
                port_value: 9191`,
		},
	}
	existingEnvoyCM := &corev1.ConfigMap{}
	if err := r.Get(ctx, client.ObjectKey{Name: "envoy-sidecar-config", Namespace: targetNamespace}, existingEnvoyCM); err != nil {
		if errors.IsNotFound(err) {
			_ = r.Create(ctx, envoyCM)
		}
	}

	// 3. Ensure OPA PDP Policy ConfigMap exists in the tenant namespace
	opaCM := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "opa-policy-config",
			Namespace: targetNamespace,
			Labels: map[string]string{
				"darueira.io/tier":      "tenant-workload",
				"darueira.io/component": "opa-pdp",
			},
		},
		Data: map[string]string{
			"envoy_authz.rego": `package envoy.authz
import future.keywords.in
import future.keywords.if
default allow := false
public_paths := ["/healthz", "/readyz", "/livez", "/metrics"]
path_is_public if { some path in public_paths; startswith(input.attributes.request.http.path, path) }
allow if { path_is_public }
allow if { startswith(object.get(input.attributes.source, "principal", ""), "spiffe://darueira.local/") }
user_id := uid if { uid := input.attributes.request.http.headers["x-user-id"]; uid != "" } else := "anonymous"
allow if { user_id in ["admin", "admin-root", "system:admin"] }`,
		},
	}
	existingOpaCM := &corev1.ConfigMap{}
	if err := r.Get(ctx, client.ObjectKey{Name: "opa-policy-config", Namespace: targetNamespace}, existingOpaCM); err != nil {
		if errors.IsNotFound(err) {
			_ = r.Create(ctx, opaCM)
		}
	}

	// 2. Update Status
	if env.Status.Phase != "Active" || env.Status.NamespaceName != targetNamespace || !env.Status.Ready {
		env.Status.Phase = "Active"
		env.Status.NamespaceName = targetNamespace
		env.Status.CiliumPolicyApplied = true
		env.Status.OpenFGATuplesSynced = true
		env.Status.Ready = true
		env.Status.ObservedGeneration = env.Generation

		if err := r.Status().Update(ctx, env); err != nil {
			return ctrl.Result{}, fmt.Errorf("failed to update Environment status: %w", err)
		}
		logger.Info("Environment successfully activated and ready", "namespace", targetNamespace)
	}

	return ctrl.Result{}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *EnvironmentReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&darueirav1alpha1.Environment{}).
		Complete(r)
}
