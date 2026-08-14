package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var cfgFile string

var rootCmd = &cobra.Command{
	Use:   "drr-ctlr-cli",
	Short: "drr-ctlr-cli - Unified CLI for Darueira Private Cloud Platform",
	Long: `drr-ctlr-cli is the operational command-line tool for developers and platform engineers
in the Darueira Private Cloud & IDP ecosystem.

It manages Tenants, Projects, Environments, and evaluates OpenFGA ReBAC permissions.`,
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func init() {
	cobra.OnInitialize(initConfig)

	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.drr-ctlr-cli.yaml)")
	rootCmd.PersistentFlags().String("gateway-url", "http://localhost:8080", "drr-iam-authz-svc gateway endpoint")
	_ = viper.BindPFlag("gateway_url", rootCmd.PersistentFlags().Lookup("gateway-url"))
}

func initConfig() {
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		home, err := os.UserHomeDir()
		cobra.CheckErr(err)

		viper.AddConfigPath(home)
		viper.SetConfigType("yaml")
		viper.SetConfigName(".drr-ctlr-cli")
	}

	viper.AutomaticEnv()
	_ = viper.ReadInConfig()
}
