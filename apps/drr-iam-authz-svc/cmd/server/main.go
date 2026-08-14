package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	adapterHttp "github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/adapter/http"
	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/adapter/oidc"
	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/adapter/openfga"
	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/config"
	"github.com/dexterity/darueira/apps/drr-iam-authz-svc/internal/service"
)

func main() {
	cfg := config.Load()
	log.Printf("[INFO] Initializing drr-iam-authz-svc on port %s", cfg.Port)

	// 1. Initialize Adapters
	fgaAdapter, err := openfga.NewOpenFGAAdapter(cfg.OpenFGAURL, cfg.StoreID, cfg.ModelID)
	if err != nil {
		log.Fatalf("[FATAL] Failed to initialize OpenFGA adapter: %v", err)
	}

	oidcValidator := oidc.NewOIDCValidator(cfg.OIDCIssuer, cfg.OIDCSecret)

	// 2. Initialize Application Core Service
	authzSvc := service.NewAuthzService(fgaAdapter, oidcValidator)

	// 3. Initialize HTTP Handlers
	mux := http.NewServeMux()
	handler := adapterHttp.NewAuthzHandler(authzSvc)
	handler.RegisterRoutes(mux)

	server := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// 4. Graceful Shutdown listener
	shutdownErr := make(chan error, 1)
	go func() {
		quit := make(chan os.Signal, 1)
		signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
		<-quit
		log.Println("[INFO] Shutting down server gracefully...")

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		shutdownErr <- server.Shutdown(ctx)
	}()

	log.Printf("[SUCCESS] drr-iam-authz-svc listening at http://0.0.0.0:%s", cfg.Port)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("[FATAL] Server error: %v", err)
	}

	if err := <-shutdownErr; err != nil {
		log.Printf("[ERROR] Graceful shutdown encountered error: %v", err)
	} else {
		log.Println("[INFO] Server stopped gracefully.")
	}
}
