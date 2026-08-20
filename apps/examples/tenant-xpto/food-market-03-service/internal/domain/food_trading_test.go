package domain

import (
	"testing"
)

func TestFoodTradingValidation(t *testing.T) {
	trading := &FoodTrading{
		MarketID:   "MKT-EU-03-GOLANG",
		ItemName:   "Dutch Gouda Cheese Wheel 10kg",
		Quantity:   15.0,
		UnitPrice:  120.0,
		TraderName: "Amsterdam Dairy Direct",
	}

	if err := trading.ValidateAndCalculate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if trading.TotalPrice != 1800.0 {
		t.Fatalf("expected total price 1800.0, got %f", trading.TotalPrice)
	}

	if trading.Status != "CONFIRMED" {
		t.Fatalf("expected status CONFIRMED, got %s", trading.Status)
	}
}

func TestFoodTradingInvalidQuantity(t *testing.T) {
	trading := &FoodTrading{
		MarketID:   "MKT-EU-03-GOLANG",
		ItemName:   "Dutch Gouda Cheese Wheel 10kg",
		Quantity:   -5.0,
		UnitPrice:  120.0,
		TraderName: "Amsterdam Dairy Direct",
	}

	if err := trading.ValidateAndCalculate(); err == nil {
		t.Fatal("expected validation error for negative quantity, got nil")
	}
}
