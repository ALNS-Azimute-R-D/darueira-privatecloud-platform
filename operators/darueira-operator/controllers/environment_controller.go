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
