package rest

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/darueira/foodmarket/service03/internal/domain"
	"github.com/darueira/foodmarket/service03/internal/port"
	"github.com/gin-gonic/gin"
)

type FoodTradingHandler struct {
	useCase  port.FoodTradingUseCase
	marketID string
}

func NewFoodTradingHandler(useCase port.FoodTradingUseCase, marketID string) *FoodTradingHandler {
	return &FoodTradingHandler{
		useCase:  useCase,
		marketID: marketID,
	}
}

func (h *FoodTradingHandler) RegisterRoutes(router *gin.Engine) {
	api := router.Group("/api/food-tradings")
	{
		api.POST("", h.CreateTrading)
		api.GET("", h.ListTradings)
		api.GET("/stream", h.StreamTradings)
	}

	// Health and OpenAPI docs
	router.GET("/healthz", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "UP", "service": "food-market-03-service", "tech": "Go / Gin"})
	})
	router.GET("/v3/api-docs", h.OpenAPISpec)
	router.GET("/swagger-ui", h.SwaggerUI)
}

func (h *FoodTradingHandler) CreateTrading(c *gin.Context) {
	var cmd domain.CreateFoodTradingCommand
	if err := c.ShouldBindJSON(&cmd); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	trading, err := h.useCase.CreateTrading(c.Request.Context(), cmd)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, trading)
}

func (h *FoodTradingHandler) ListTradings(c *gin.Context) {
	list, err := h.useCase.ListTradings(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if list == nil {
		list = []domain.FoodTrading{}
	}
	c.JSON(http.StatusOK, list)
}

func (h *FoodTradingHandler) StreamTradings(c *gin.Context) {
	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache, no-transform")
	c.Writer.Header().Set("Connection", "keep-alive")
	c.Writer.Header().Set("X-Accel-Buffering", "no")
	c.Writer.Header().Set("Access-Control-Allow-Origin", "*")

	ch := h.useCase.SubscribeStream()
	defer h.useCase.UnsubscribeStream(ch)

	// Send initial connection event
	c.SSEvent("INIT", "Connected to Food Trading Live SSE Stream (Service 03 - Go/Gin)")
	c.Writer.Flush()

	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	c.Stream(func(w io.Writer) bool {
		select {
		case <-c.Request.Context().Done():
			return false
		case <-ticker.C:
			fmt.Fprintf(w, ": ping\n\n")
			return true
		case trading, ok := <-ch:
			if !ok {
				return false
			}
			data, _ := json.Marshal(trading)
			fmt.Fprintf(w, "event: FOOD_TRADING_EVENT\ndata: %s\n\n", string(data))
			return true
		}
	})
}

func (h *FoodTradingHandler) OpenAPISpec(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"openapi": "3.0.3",
		"info": gin.H{
			"title":       "Food Market 03 Service API (Go 1.23 / Gin)",
			"version":     "1.0.0",
			"description": "Hexagonal Architecture REST API & SSE Stream for European Food Marketplaces in Go (Tenant: swfabrik-europe, Market: " + h.marketID + ")",
		},
		"paths": gin.H{
			"/api/food-tradings": gin.H{
				"post": gin.H{
					"summary": "F01.1: Create Food Trading in Go",
				},
				"get": gin.H{
					"summary": "F01.2: List Food Tradings from schema schm03",
				},
			},
			"/api/food-tradings/stream": gin.H{
				"get": gin.H{
					"summary": "F01.3: Real-Time SSE Stream of Food Trading Events",
				},
			},
		},
	})
}

func (h *FoodTradingHandler) SwaggerUI(c *gin.Context) {
	html := `<!DOCTYPE html><html><head><title>Food Market 03 - Swagger UI</title>
<link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head><body><div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: "/v3/api-docs", dom_id: "#swagger-ui"});</script>
</body></html>`
	c.Data(http.StatusOK, "text/html; charset=utf-8", []byte(html))
}
