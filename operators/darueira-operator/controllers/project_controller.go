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

// ProjectReconciler reconciles a Project object
type ProjectReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

// +kubebuilder:rbac:groups=darueira.io,resources=projects,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=darueira.io,resources=projects/status,verbs=get;update;patch

func (r *ProjectReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	project := &darueirav1alpha1.Project{}
	if err := r.Get(ctx, req.NamespacedName, project); err != nil {
		if errors.IsNotFound(err) {
			logger.Info("Project resource deleted", "project", req.Name)
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, fmt.Errorf("failed to get Project: %w", err)
	}

	logger.Info("Reconciling Project", "name", project.Name, "tenant", project.Spec.TenantRef, "owner", project.Spec.OwnerEmail)

	// Update status
	if project.Status.Phase != "Active" {
		project.Status.Phase = "Active"
		project.Status.OpenFGATuplesSynced = true
		project.Status.ObservedGeneration = project.Generation
		if err := r.Status().Update(ctx, project); err != nil {
			return ctrl.Result{}, fmt.Errorf("failed to update Project status: %w", err)
		}
		logger.Info("Project activated successfully", "project", project.Name)
	}

	return ctrl.Result{}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *ProjectReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&darueirav1alpha1.Project{}).
		Complete(r)
}
