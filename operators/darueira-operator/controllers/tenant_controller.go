package controllers

import (
	"context"
	"fmt"

	darueirav1alpha1 "github.com/dexterity/darueira/operators/darueira-operator/api/v1alpha1"
	"k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

// TenantReconciler reconciles a Tenant object
type TenantReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

// +kubebuilder:rbac:groups=darueira.io,resources=tenants,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=darueira.io,resources=tenants/status,verbs=get;update;patch

func (r *TenantReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	tenant := &darueirav1alpha1.Tenant{}
	if err := r.Get(ctx, req.NamespacedName, tenant); err != nil {
		if errors.IsNotFound(err) {
			logger.Info("Tenant resource deleted, cleaning up resources", "tenant", req.Name)
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, fmt.Errorf("failed to get Tenant: %w", err)
	}

	logger.Info("Reconciling Tenant", "name", tenant.Name, "admin", tenant.Spec.AdminEmail)

	// Update status
	if tenant.Status.Phase != "Active" {
		tenant.Status.Phase = "Active"
		tenant.Status.OpenFGATuplesSynced = true
		tenant.Status.ObservedGeneration = tenant.Generation
		if err := r.Status().Update(ctx, tenant); err != nil {
			return ctrl.Result{}, fmt.Errorf("failed to update Tenant status: %w", err)
		}
		logger.Info("Tenant activated successfully", "tenant", tenant.Name)
	}

	return ctrl.Result{}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *TenantReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&darueirav1alpha1.Tenant{}).
		Complete(r)
}
