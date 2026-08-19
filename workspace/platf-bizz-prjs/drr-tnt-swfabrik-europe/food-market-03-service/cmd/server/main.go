package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/darueira/foodmarket/service03/internal/adapter/in/messaging"
	"github.com/darueira/foodmarket/service03/internal/adapter/in/rest"
	"github.com/darueira/foodmarket/service03/internal/adapter/out/persistence"
	outMessaging "github.com/darueira/foodmarket/service03/internal/adapter/out/messaging"
	"github.com/darueira/foodmarket/service03/internal/adapter/out/sse"
	"github.com/darueira/foodmarket/service03/internal/application"
	"github.com/gin-gonic/gin"
	_ "github.com/lib/pq"
)

func getEnv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}

func main() {
	log.Println("==================================================================")
	log.Println("  Food Market 03 Service - Go 1.23 / Gin / Hexagonal Architecture ")
	log.Println("==================================================================")

	port := getEnv("PORT", "8083")
	pgURL := getEnv("DATABASE_URL", "postgres://drr_admin:change-me-in-openbao@central-postgres.drr-corpshared-plat.svc.cluster.local:5432/drr_tnt_bizapps_db?sslmode=disable&search_path=schm03")
	rmqHost := getEnv("RABBITMQ_HOST", "message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local")
	rmqPort := getEnv("RABBITMQ_PORT", "5672")
	rmqUser := getEnv("RABBITMQ_USER", "drr_admin")
	rmqPass := getEnv("RABBITMQ_PASS", "darueira-admin123")
	rmqVHost := getEnv("RABBITMQ_VHOST", "/")
	marketID := getEnv("APP_MARKET_ID", "MKT-EU-03-GOLANG")
	rmqTopic := getEnv("APP_RABBITMQ_TOPIC", "marketplace.foodtrading.topic")
	rmqQueue := getEnv("APP_RABBITMQ_QUEUE", "marketplace.foodtrading.queue01")

	if rmqVHost == "/" {
		rmqVHost = ""
	}
	amqpURI := fmt.Sprintf("amqp://%s:%s@%s:%s/%s", rmqUser, rmqPass, rmqHost, rmqPort, rmqVHost)

	// 1. Connect to PostgreSQL
	db, err := sql.Open("postgres", pgURL)
	if err != nil {
		log.Fatalf("Failed to open DB connection: %v", err)
	}
	defer db.Close()
	db.SetMaxOpenConns(20)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	for i := 0; i < 10; i++ {
		if err := db.Ping(); err == nil {
			log.Println("[Go 03] Connected to PostgreSQL (schema schm03)")
			break
		}
		time.Sleep(1 * time.Second)
	}

	// 2. Initialize Hexagonal Adapters
	postgresAdapter := persistence.NewPostgresAdapter(db)
	sseBroadcaster := sse.NewBroadcaster()
	rmqPublisher := outMessaging.NewRabbitMQPublisher(amqpURI, rmqTopic)
	defer rmqPublisher.Close()

	// 3. Initialize Application Service
	appService := application.NewFoodTradingService(
		postgresAdapter,
		rmqPublisher,
		sseBroadcaster,
		marketID,
	)

	// 4. Start RabbitMQ Inbound Consumer
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	rmqConsumer := messaging.NewRabbitMQConsumer(amqpURI, rmqQueue, appService)
	rmqConsumer.Start(ctx)
	defer rmqConsumer.Stop()

	// 5. Setup Gin Router
	gin.SetMode(gin.ReleaseMode)
	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	})

	handler := rest.NewFoodTradingHandler(appService, marketID)
	handler.RegisterRoutes(router)

	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}

	go func() {
		log.Printf("[Go 03] HTTP Server listening on port :%s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP server failed: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("[Go 03] Shutting down gracefully...")

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	_ = srv.Shutdown(shutdownCtx)
}
