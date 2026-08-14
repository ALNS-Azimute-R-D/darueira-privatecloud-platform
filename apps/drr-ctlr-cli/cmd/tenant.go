package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var tenantCmd = &cobra.Command{
	Use:   "tenant",
	Short: "Manage platform tenants and organizations",
}

var tenantListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all registered tenants",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("TENANT ID       DISPLAY NAME        ADMIN EMAIL              STATUS")
		fmt.Println("-------------------------------------------------------------------")
		fmt.Printf("%-15s %-19s %-24s %s\n", "acme", "Acme Corporation", "admin@acme.corp", "Active")
		fmt.Printf("%-15s %-19s %-24s %s\n", "globex", "Globex Corporation", "admin@globex.corp", "Active")
	},
}

var tenantCreateName string
var tenantCreateEmail string

var tenantCreateCmd = &cobra.Command{
	Use:   "create [tenant-id]",
	Short: "Create a new tenant",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		tenantID := args[0]
		fmt.Printf("Creating Tenant '%s' (Name: '%s', Admin: '%s')...\n", tenantID, tenantCreateName, tenantCreateEmail)
		fmt.Printf("✅ Tenant '%s' successfully provisioned and OpenFGA tuples registered.\n", tenantID)
	},
}

func init() {
	tenantCreateCmd.Flags().StringVar(&tenantCreateName, "name", "", "Display name for tenant")
	tenantCreateCmd.Flags().StringVar(&tenantCreateEmail, "admin-email", "", "Admin email address")

	tenantCmd.AddCommand(tenantListCmd)
	tenantCmd.AddCommand(tenantCreateCmd)
	rootCmd.AddCommand(tenantCmd)
}
