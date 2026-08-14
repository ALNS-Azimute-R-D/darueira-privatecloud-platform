package cmd

import (
	"fmt"
	"runtime"

	"github.com/spf13/cobra"
)

var (
	Version   = "v0.2.0-phase2"
	BuildDate = "2026-08-14"
	GitCommit = "dev"
)

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print drr-ctlr-cli and platform version information",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("drr-ctlr-cli version:   %s\n", Version)
		fmt.Printf("Git commit:       %s\n", GitCommit)
		fmt.Printf("Build date:       %s\n", BuildDate)
		fmt.Printf("Go version:       %s\n", runtime.Version())
		fmt.Printf("OS/Arch:          %s/%s\n", runtime.GOOS, runtime.GOARCH)
	},
}

func init() {
	rootCmd.AddCommand(versionCmd)
}
