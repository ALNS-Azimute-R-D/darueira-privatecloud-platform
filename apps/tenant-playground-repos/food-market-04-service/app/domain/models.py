from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import uuid

@dataclass
class FoodTrading:
    item_name: str
    quantity: Decimal
    unit_price: Decimal
    trader_name: str
    market_id: str
    id: int | None = None
    trading_id: str = ""
    total_price: Decimal = Decimal("0.00")
    status: str = "CONFIRMED"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def validate_and_calculate(self):
        if not self.item_name or not self.item_name.strip():
            raise ValueError("itemName must not be blank")
        if self.quantity <= Decimal("0.00"):
            raise ValueError("quantity must be greater than zero")
        if self.unit_price <= Decimal("0.00"):
            raise ValueError("unitPrice must be greater than zero")
        if not self.trader_name or not self.trader_name.strip():
            raise ValueError("traderName must not be blank")
        if not self.trading_id:
            self.trading_id = f"TRD-PY-{uuid.uuid4().hex[:8].upper()}"
        self.total_price = self.quantity * self.unit_price

@dataclass
class FoodTradingEvent:
    trading_id: str
    market_id: str
    item_name: str
    quantity: Decimal
    unit_price: Decimal
    total_price: Decimal
    trader_name: str
    status: str = "CONFIRMED"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "FOOD_TRADING_CREATED"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class CreateFoodTradingCommand:
    item_name: str
    quantity: Decimal
    unit_price: Decimal
    trader_name: str
