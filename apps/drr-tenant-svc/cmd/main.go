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

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/authz"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/events"
	httpAdapter "github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/http"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/adapter/memory"
	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/service"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8081"
	}
	authzBaseURL := os.Getenv("DRR_AUTHZ_URL")
	kafkaTopic := os.Getenv("KAFKA_TOPIC")

	fmt.Println("=================================================================")
	fmt.Println("  Darueira Platform - Tenant & Project Management Service        ")
	fmt.Println("  (drr-tenant-svc / Clean Hexagonal Architecture)                ")
	fmt.Println("=================================================================")

	// 1. Initialize Adapters
	tenantRepo := memory.NewInMemoryTenantRepo()
	projectRepo := memory.NewInMemoryProjectRepo()
	memberRepo := memory.NewInMemoryMemberRepo()
	eventPublisher := events.NewLoggingEventPublisher(kafkaTopic)
	authzClient := authz.NewHTTPAuthzClient(authzBaseURL)

	// 2. Initialize Core Application Services
	tenantSvc := service.NewTenantService(tenantRepo, eventPublisher, authzClient)
	projectSvc := service.NewProjectService(projectRepo, tenantRepo, eventPublisher, authzClient)
	memberSvc := service.NewMemberService(memberRepo, tenantRepo, eventPublisher, authzClient)

	// 3. Seed Default Master/Platform Tenant
	ctx := context.Background()
	_, _ = tenantSvc.CreateTenant(ctx, service.CreateTenantInput{
		ID:          "darueira-corp",
		Name:        "darueira-corp",
		DisplayName: "Darueira Enterprise Root",
		Description: "Platform Shared Services & Root Organization",
		AdminUserID: "admin-root",
	})
	_, _ = projectSvc.CreateProject(ctx, service.CreateProjectInput{
		ID:          "platform-core",
		TenantID:    "darueira-corp",
		Name:        "platform-core",
		Description: "Core platform shared projects and infrastructure",
		OwnerUserID: "admin-root",
	})

	// 4. HTTP Router
	router := httpAdapter.NewRouter(tenantSvc, projectSvc, memberSvc)

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	go func() {
		log.Printf("[HTTP] drr-tenant-svc listening on port :%s", port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("[HTTP] Server failed: %v", err)
		}
	}()

	// Graceful Shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("[SHUTDOWN] Shutting down drr-tenant-svc gracefully...")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("[SHUTDOWN] Server forced to shutdown: %v", err)
	}
	log.Println("[SHUTDOWN] drr-tenant-svc terminated cleanly.")
}
