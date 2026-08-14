package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// TenantResourceQuotaSpec specifies quota allocated for the tenant
type TenantResourceQuotaSpec struct {
	CPU     string `json:"cpu,omitempty"`
	Memory  string `json:"memory,omitempty"`
	Storage string `json:"storage,omitempty"`
	MaxPods int32  `json:"maxPods,omitempty"`
}

// TenantSpec defines the desired state of Tenant
type TenantSpec struct {
	DisplayName   string                  `json:"displayName"`
	AdminEmail    string                  `json:"adminEmail"`
	Description   string                  `json:"description,omitempty"`
	ResourceQuota TenantResourceQuotaSpec `json:"resourceQuota,omitempty"`
	Enabled       bool                    `json:"enabled,omitempty"`
}

// TenantStatus defines the observed state of Tenant
type TenantStatus struct {
	Phase                string             `json:"phase,omitempty"`
	ActiveProjectsCount  int32              `json:"activeProjectsCount,omitempty"`
	OpenFGATuplesSynced  bool               `json:"openFGATuplesSynced,omitempty"`
	Conditions           []metav1.Condition `json:"conditions,omitempty"`
	ObservedGeneration   int64              `json:"observedGeneration,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:scope=Cluster
// Tenant is the Schema for the tenants API
type Tenant struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   TenantSpec   `json:"spec,omitempty"`
	Status TenantStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
// TenantList contains a list of Tenant
type TenantList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []Tenant `json:"items"`
}

func init() {
	SchemeBuilder.Register(&Tenant{}, &TenantList{})
}
