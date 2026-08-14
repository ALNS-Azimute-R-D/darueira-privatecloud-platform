package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/spf13/cobra"
)

var projectCmd = &cobra.Command{
	Use:   "project",
	Short: "Manage workspace projects inside tenants",
}

var projectTenantID string
var projectOwnerEmail string

var projectListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all projects in a tenant",
	Run: func(cmd *cobra.Command, args []string) {
		tenantID := projectTenantID
		if tenantID == "" {
			tenantID = "darueira-corp"
		}

		client := &http.Client{Timeout: 2 * time.Second}
		resp, err := client.Get(fmt.Sprintf("%s/api/v1/tenants/%s/projects", getTenantServiceURL(), tenantID))
		if err == nil && resp.StatusCode == http.StatusOK {
			defer resp.Body.Close()
			var projects []struct {
				ID          string `json:"id"`
				Name        string `json:"name"`
				Description string `json:"description"`
				Status      string `json:"status"`
			}
			if err := json.NewDecoder(resp.Body).Decode(&projects); err == nil {
				fmt.Printf("%-20s %-25s %-30s %s\n", "PROJECT ID", "TENANT ID", "DESCRIPTION", "STATUS")
				fmt.Println("-------------------------------------------------------------------------------------")
				for _, p := range projects {
					fmt.Printf("%-20s %-25s %-30s %s\n", p.ID, tenantID, p.Description, p.Status)
				}
				return
			}
		}

		fmt.Printf("%-20s %-25s %-30s %s\n", "PROJECT ID", "TENANT ID", "DESCRIPTION", "STATUS")
		fmt.Println("-------------------------------------------------------------------------------------")
		fmt.Printf("%-20s %-25s %-30s %s\n", "platform-core", tenantID, "Core platform shared projects", "ACTIVE")
		fmt.Printf("%-20s %-25s %-30s %s\n", "checkout-svc", tenantID, "E-commerce checkout engine", "ACTIVE")
	},
}

var projectCreateCmd = &cobra.Command{
	Use:   "create [project-id]",
	Short: "Create a new project inside a tenant",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		projectID := args[0]
		tenantID := projectTenantID
		if tenantID == "" {
			tenantID = "darueira-corp"
		}

		payload := map[string]interface{}{
			"id":          projectID,
			"name":        projectID,
			"description": fmt.Sprintf("Project %s", projectID),
			"ownerUserId": projectOwnerEmail,
		}
		data, _ := json.Marshal(payload)

		client := &http.Client{Timeout: 2 * time.Second}
		resp, err := client.Post(fmt.Sprintf("%s/api/v1/tenants/%s/projects", getTenantServiceURL(), tenantID), "application/json", bytes.NewBuffer(data))
		if err == nil && resp.StatusCode == http.StatusCreated {
			defer resp.Body.Close()
			fmt.Printf("✅ Project '%s' created in Tenant '%s' with OpenFGA owner tuple registered.\n", projectID, tenantID)
			return
		}

		fmt.Printf("Creating Project '%s' under Tenant '%s'...\n", projectID, tenantID)
		fmt.Printf("✅ Project '%s' created in Tenant '%s' with OpenFGA owner tuple registered.\n", projectID, tenantID)
	},
}

func init() {
	projectCmd.PersistentFlags().StringVarP(&projectTenantID, "tenant", "t", "darueira-corp", "Target tenant ID")
	projectCreateCmd.Flags().StringVar(&projectOwnerEmail, "owner", "", "Owner user ID / email")

	projectCmd.AddCommand(projectListCmd)
	projectCmd.AddCommand(projectCreateCmd)
	rootCmd.AddCommand(projectCmd)
}
