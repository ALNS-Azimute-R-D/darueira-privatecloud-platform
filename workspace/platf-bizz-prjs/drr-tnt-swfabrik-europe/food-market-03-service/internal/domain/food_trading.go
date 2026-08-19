package domain

import (
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

type FoodTrading struct {
	ID         int64     `json:"id"`
	TradingID  string    `json:"tradingId"`
	MarketID   string    `json:"marketId"`
	ItemName   string    `json:"itemName"`
	Quantity   float64   `json:"quantity"`
	UnitPrice  float64   `json:"unitPrice"`
	TotalPrice float64   `json:"totalPrice"`
	TraderName string    `json:"traderName"`
	Status     string    `json:"status"`
	CreatedAt  time.Time `json:"createdAt"`
}

func (f *FoodTrading) ValidateAndCalculate() error {
	if strings.TrimSpace(f.ItemName) == "" {
		return errors.New("itemName must not be blank")
	}
	if f.Quantity <= 0 {
		return errors.New("quantity must be greater than zero")
	}
	if f.UnitPrice <= 0 {
		return errors.New("unitPrice must be greater than zero")
	}
	if strings.TrimSpace(f.TraderName) == "" {
		return errors.New("traderName must not be blank")
	}
	if strings.TrimSpace(f.TradingID) == "" {
		f.TradingID = fmt.Sprintf("TRD-GO-%s", strings.ToUpper(uuid.New().String()[:8]))
	}
	if strings.TrimSpace(f.Status) == "" {
		f.Status = "CONFIRMED"
	}
	if f.CreatedAt.IsZero() {
		f.CreatedAt = time.Now().UTC()
	}
	f.TotalPrice = f.Quantity * f.UnitPrice
	return nil
}

type FoodTradingEvent struct {
	EventID    string    `json:"eventId"`
	EventType  string    `json:"eventType"`
	TradingID  string    `json:"tradingId"`
	MarketID   string    `json:"marketId"`
	ItemName   string    `json:"itemName"`
	Quantity   float64   `json:"quantity"`
	UnitPrice  float64   `json:"unitPrice"`
	TotalPrice float64   `json:"totalPrice"`
	TraderName string    `json:"traderName"`
	Status     string    `json:"status"`
	Timestamp  time.Time `json:"timestamp"`
}

type CreateFoodTradingCommand struct {
	ItemName   string  `json:"itemName"`
	Quantity   float64 `json:"quantity"`
	UnitPrice  float64 `json:"unitPrice"`
	TraderName string  `json:"traderName"`
}
