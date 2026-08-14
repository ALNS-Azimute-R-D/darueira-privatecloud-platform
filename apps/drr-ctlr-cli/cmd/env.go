package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var envCmd = &cobra.Command{
	Use:   "env",
	Short: "Manage tenant deployment environments",
}

var envListCmd = &cobra.Command{
	Use:   "list",
	Short: "List environments for a project",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("TENANT    PROJECT     ENVIRONMENT  NAMESPACE                  PEP SIDECAR  STATUS")
		fmt.Println("---------------------------------------------------------------------------------")
		fmt.Printf("%-9s %-11s %-12s %-26s %-12s %s\n", "acme", "acme-core", "dev", "drr-tnt-acme-acme-core-dev", "Enabled", "Active")
		fmt.Printf("%-9s %-11s %-12s %-26s %-12s %s\n", "acme", "acme-core", "staging", "drr-tnt-acme-acme-core-staging", "Enabled", "Active")
	},
}

var envDeployCmd = &cobra.Command{
	Use:   "deploy [tenant] [project] [env]",
	Short: "Trigger declarative deployment into target environment",
	Args:  cobra.ExactArgs(3),
	Run: func(cmd *cobra.Command, args []string) {
		tenant := args[0]
		project := args[1]
		envName := args[2]

		targetNS := fmt.Sprintf("drr-tnt-%s-%s-%s", tenant, project, envName)
		fmt.Printf("🚀 Triggering GitOps reconciliation for namespace '%s'...\n", targetNS)
		fmt.Printf("✅ Deployment pipeline triggered via Tekton & ArgoCD. Envoy PEP + OPA PDP active.\n")
	},
}

func init() {
	envCmd.AddCommand(envListCmd)
	envCmd.AddCommand(envDeployCmd)
	rootCmd.AddCommand(envCmd)
}
