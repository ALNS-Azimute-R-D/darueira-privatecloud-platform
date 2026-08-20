package application

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/darueira/foodmarket/service03/internal/domain"
	"github.com/darueira/foodmarket/service03/internal/port"
	"github.com/google/uuid"
)

type FoodTradingService struct {
	persistence    port.FoodTradingPersistencePort
	publisher      port.FoodTradingEventPublisherPort
	sseBroadcaster port.FoodTradingSseBroadcasterPort
	marketID       string
}

func NewFoodTradingService(
	p port.FoodTradingPersistencePort,
	pub port.FoodTradingEventPublisherPort,
	sse port.FoodTradingSseBroadcasterPort,
	marketID string,
) *FoodTradingService {
	return &FoodTradingService{
		persistence:    p,
		publisher:      pub,
		sseBroadcaster: sse,
		marketID:       marketID,
	}
}

func (s *FoodTradingService) CreateTrading(ctx context.Context, cmd domain.CreateFoodTradingCommand) (*domain.FoodTrading, error) {
	log.Printf("[Go 03] Creating food trading: %s by %s", cmd.ItemName, cmd.TraderName)

	trading := &domain.FoodTrading{
		MarketID:   s.marketID,
		ItemName:   cmd.ItemName,
		Quantity:   cmd.Quantity,
		UnitPrice:  cmd.UnitPrice,
		TraderName: cmd.TraderName,
		Status:     "CONFIRMED",
		CreatedAt:  time.Now().UTC(),
	}

	if err := trading.ValidateAndCalculate(); err != nil {
		return nil, err
	}

	// 1. Persist to PostgreSQL (F02)
	saved, err := s.persistence.Save(ctx, trading)
	if err != nil {
		return nil, fmt.Errorf("failed to persist trading: %w", err)
	}

	// 2. Publish to RabbitMQ Topic (F03)
	event := domain.FoodTradingEvent{
		EventID:    uuid.New().String(),
		EventType:  "FOOD_TRADING_CREATED",
		TradingID:  saved.TradingID,
		MarketID:   saved.MarketID,
		ItemName:   saved.ItemName,
		Quantity:   saved.Quantity,
		UnitPrice:  saved.UnitPrice,
		TotalPrice: saved.TotalPrice,
		TraderName: saved.TraderName,
		Status:     saved.Status,
		Timestamp:  time.Now().UTC(),
	}

	if err := s.publisher.PublishEvent(ctx, event); err != nil {
		log.Printf("[Go 03] Warning: failed to publish to RabbitMQ: %v", err)
	}

	// 3. Broadcast to SSE (F01.3 / F04.2.3)
	s.sseBroadcaster.Broadcast(*saved)

	return saved, nil
}

func (s *FoodTradingService) ListTradings(ctx context.Context) ([]domain.FoodTrading, error) {
	return s.persistence.FindAll(ctx)
}

func (s *FoodTradingService) SubscribeStream() <-chan domain.FoodTrading {
	return s.sseBroadcaster.Subscribe()
}

func (s *FoodTradingService) UnsubscribeStream(ch <-chan domain.FoodTrading) {
	s.sseBroadcaster.Unsubscribe(ch)
}

func (s *FoodTradingService) ProcessIncomingEvent(ctx context.Context, event domain.FoodTradingEvent) error {
	log.Printf("[Go 03] Consuming RabbitMQ message event: %s", event.TradingID)

	if event.Quantity <= 0 || event.UnitPrice <= 0 {
		log.Printf("[Go 03] Discarded invalid event: %s", event.TradingID)
		return errors.New("invalid event payload")
	}

	// Check idempotency
	existing, err := s.persistence.FindByTradingID(ctx, event.TradingID)
	if err == nil && existing != nil {
		log.Printf("[Go 03] Trading %s already exists in DB, skipping duplicate persist", event.TradingID)
		return nil
	}

	mktID := event.MarketID
	if strings.TrimSpace(mktID) == "" {
		mktID = s.marketID
	}

	trading := &domain.FoodTrading{
		TradingID:  event.TradingID,
		MarketID:   mktID,
		ItemName:   event.ItemName,
		Quantity:   event.Quantity,
		UnitPrice:  event.UnitPrice,
		TraderName: event.TraderName,
		Status:     "CONFIRMED",
		CreatedAt:  event.Timestamp,
	}

	if err := trading.ValidateAndCalculate(); err != nil {
		return err
	}

	saved, err := s.persistence.Save(ctx, trading)
	if err != nil {
		return err
	}

	s.sseBroadcaster.Broadcast(*saved)
	return nil
}
