from decimal import Decimal
import pytest
from app.domain.models import FoodTrading

def test_food_trading_validation():
    trading = FoodTrading(
        market_id="MKT-EU-04-PYTHON",
        item_name="French Dijon Mustard 1kg",
        quantity=Decimal("50.00"),
        unit_price=Decimal("12.50"),
        trader_name="Normandie Fine Foods",
    )
    trading.validate_and_calculate()

    assert trading.trading_id.startswith("TRD-PY-")
    assert trading.total_price == Decimal("625.0000") or trading.total_price == Decimal("625.00")
    assert trading.status == "CONFIRMED"

def test_food_trading_invalid_quantity():
    trading = FoodTrading(
        market_id="MKT-EU-04-PYTHON",
        item_name="French Dijon Mustard 1kg",
        quantity=Decimal("-1.00"),
        unit_price=Decimal("12.50"),
        trader_name="Normandie Fine Foods",
    )
    with pytest.raises(ValueError):
        trading.validate_and_calculate()
