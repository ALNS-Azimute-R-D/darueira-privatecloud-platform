package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/authz"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/events"
	httpAdapter "github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/http"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/k8s"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/adapter/memory"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/domain"
	"github.com/dexterity/darueira/apps/drr-env-orchestrator-svc/internal/service"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8082"
	}
	authzBaseURL := os.Getenv("DRR_AUTHZ_URL")
	kafkaTopic := os.Getenv("KAFKA_TOPIC")

	fmt.Println("=================================================================")
	fmt.Println("  Darueira Platform - Environment Orchestration Service          ")
	fmt.Println("  (drr-env-orchestrator-svc / Clean Hexagonal Architecture)      ")
	fmt.Println("=================================================================")

	// 1. Initialize Adapters
	envRepo := memory.NewInMemoryEnvRepo()
	k8sApplier := k8s.NewDirectK8sApplier()
	eventPublisher := events.NewLoggingEventPublisher(kafkaTopic)
	authzClient := authz.NewHTTPAuthzClient(authzBaseURL)

	// 2. Initialize Core Application Service
	orchSvc := service.NewOrchestratorService(envRepo, k8sApplier, eventPublisher, authzClient)

	// 3. Seed Default Shared Environment
	ctx := context.Background()
	_, _ = orchSvc.CreateEnvironment(ctx, service.CreateEnvironmentInput{
		TenantID:       "darueira-corp",
		ProjectID:      "platform-core",
		Name:           "dev",
		Type:           domain.EnvTypeDev,
		OperatorUserID: "admin-root",
	})

	// 4. HTTP Router
	router := httpAdapter.NewRouter(orchSvc)

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	go func() {
		log.Printf("[HTTP] drr-env-orchestrator-svc listening on port :%s", port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("[HTTP] Server failed: %v", err)
		}
	}()

	// Graceful Shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("[SHUTDOWN] Shutting down drr-env-orchestrator-svc gracefully...")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("[SHUTDOWN] Server forced to shutdown: %v", err)
	}
	log.Println("[SHUTDOWN] drr-env-orchestrator-svc terminated cleanly.")
}
