package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// EnvironmentType represents deployment lifecycle tier
type EnvironmentType string

const (
	EnvDev     EnvironmentType = "dev"
	EnvStaging EnvironmentType = "staging"
	EnvProd    EnvironmentType = "prod"
)

// EnvironmentSpec defines the desired state of Environment
type EnvironmentSpec struct {
	TenantRef      string          `json:"tenantRef"`
	ProjectRef     string          `json:"projectRef"`
	Type           EnvironmentType `json:"type"`
	Deployers      []string        `json:"deployers,omitempty"`
	Operators      []string        `json:"operators,omitempty"`
	EnableSidecarPEP bool          `json:"enableSidecarPEP,omitempty"`
}

// EnvironmentStatus defines the observed state of Environment
type EnvironmentStatus struct {
	Phase                string             `json:"phase,omitempty"`
	NamespaceName        string             `json:"namespaceName,omitempty"`
	CiliumPolicyApplied  bool               `json:"ciliumPolicyApplied,omitempty"`
	OpenFGATuplesSynced  bool               `json:"openFGATuplesSynced,omitempty"`
	Ready                bool               `json:"ready,omitempty"`
	Conditions           []metav1.Condition `json:"conditions,omitempty"`
	ObservedGeneration   int64              `json:"observedGeneration,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:scope=Cluster
// Environment is the Schema for the environments API
type Environment struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   EnvironmentSpec   `json:"spec,omitempty"`
	Status EnvironmentStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
// EnvironmentList contains a list of Environment
type EnvironmentList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []Environment `json:"items"`
}

func init() {
	SchemeBuilder.Register(&Environment{}, &EnvironmentList{})
}
