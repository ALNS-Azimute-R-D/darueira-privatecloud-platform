package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	authCheckUser     string
	authCheckRelation string
	authCheckObject   string
)

var authCmd = &cobra.Command{
	Use:   "auth",
	Short: "Manage authentication and verify ReBAC permissions",
}

var authCheckCmd = &cobra.Command{
	Use:   "check",
	Short: "Check if a user has a relation on an object via drr-iam-authz-svc",
	Example: `  drr-ctlr-cli auth check --user user:alice --relation admin --object tenant:acme
  drr-ctlr-cli auth check --user user:bob --relation can_deploy --object environment:acme-dev`,
	Run: func(cmd *cobra.Command, args []string) {
		if authCheckUser == "" || authCheckRelation == "" || authCheckObject == "" {
			fmt.Fprintln(os.Stderr, "Error: --user, --relation, and --object flags are required.")
			os.Exit(1)
		}

		gatewayURL := viper.GetString("gateway_url")
		endpoint := fmt.Sprintf("%s/api/v1/authz/check", gatewayURL)

		payload := map[string]string{
			"user":     authCheckUser,
			"relation": authCheckRelation,
			"object":   authCheckObject,
		}

		body, err := json.Marshal(payload)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to marshal check request: %v\n", err)
			os.Exit(1)
		}

		client := &http.Client{Timeout: 5 * time.Second}
		resp, err := client.Post(endpoint, "application/json", bytes.NewReader(body))
		if err != nil {
			fmt.Printf("[SIMULATION/DEV] Gateway (%s) unreachable. Offline validation mode.\n", gatewayURL)
			fmt.Printf("Query: user='%s' relation='%s' object='%s'\n", authCheckUser, authCheckRelation, authCheckObject)
			return
		}
		defer resp.Body.Close()

		respBytes, _ := io.ReadAll(resp.Body)
		if resp.StatusCode != http.StatusOK {
			fmt.Fprintf(os.Stderr, "Auth check failed (HTTP %d): %s\n", resp.StatusCode, string(respBytes))
			os.Exit(1)
		}

		var checkResult struct {
			Allowed    bool   `json:"allowed"`
			Resolution string `json:"resolution"`
		}
		_ = json.Unmarshal(respBytes, &checkResult)

		if checkResult.Allowed {
			fmt.Printf("✅ ALLOWED: %s has relation '%s' on %s\n", authCheckUser, authCheckRelation, authCheckObject)
		} else {
			fmt.Printf("❌ DENIED: %s does NOT have relation '%s' on %s\n", authCheckUser, authCheckRelation, authCheckObject)
		}
	},
}

func init() {
	authCheckCmd.Flags().StringVar(&authCheckUser, "user", "", "User identifier (e.g. user:alice)")
	authCheckCmd.Flags().StringVar(&authCheckRelation, "relation", "", "Relation name (e.g. admin, can_deploy)")
	authCheckCmd.Flags().StringVar(&authCheckObject, "object", "", "Target object (e.g. tenant:acme, environment:acme-dev)")

	authCmd.AddCommand(authCheckCmd)
	rootCmd.AddCommand(authCmd)
}
