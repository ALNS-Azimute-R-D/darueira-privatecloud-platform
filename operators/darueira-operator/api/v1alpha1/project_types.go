package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// ProjectSpec defines the desired state of Project
type ProjectSpec struct {
	TenantRef   string   `json:"tenantRef"`
	OwnerEmail  string   `json:"ownerEmail"`
	Maintainers []string `json:"maintainers,omitempty"`
	Description string   `json:"description,omitempty"`
	Enabled     bool     `json:"enabled,omitempty"`
}

// ProjectStatus defines the observed state of Project
type ProjectStatus struct {
	Phase                   string             `json:"phase,omitempty"`
	ActiveEnvironmentsCount int32              `json:"activeEnvironmentsCount,omitempty"`
	OpenFGATuplesSynced     bool               `json:"openFGATuplesSynced,omitempty"`
	Conditions              []metav1.Condition `json:"conditions,omitempty"`
	ObservedGeneration      int64              `json:"observedGeneration,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:scope=Cluster
// Project is the Schema for the projects API
type Project struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   ProjectSpec   `json:"spec,omitempty"`
	Status ProjectStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
// ProjectList contains a list of Project
type ProjectList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []Project `json:"items"`
}

func init() {
	SchemeBuilder.Register(&Project{}, &ProjectList{})
}
