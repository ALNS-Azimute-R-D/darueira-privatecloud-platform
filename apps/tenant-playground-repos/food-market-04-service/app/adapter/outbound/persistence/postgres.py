import asyncpg
from decimal import Decimal
from typing import List, Optional
from app.domain.models import FoodTrading
from app.port.outbound import FoodTradingPersistencePort

class PostgresAdapter(FoodTradingPersistencePort):
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, trading: FoodTrading) -> FoodTrading:
        query = """
            INSERT INTO schm04.tb_food_trading 
            (trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            trading_id_val = await conn.fetchval(
                query,
                trading.trading_id,
                trading.market_id,
                trading.item_name,
                trading.quantity,
                trading.unit_price,
                trading.total_price,
                trading.trader_name,
                trading.status,
                trading.created_at,
            )
            trading.id = trading_id_val
        return trading

    async def find_all(self) -> List[FoodTrading]:
        query = """
            SELECT id, trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at
            FROM schm04.tb_food_trading
            ORDER BY id DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [
                FoodTrading(
                    id=row["id"],
                    trading_id=row["trading_id"],
                    market_id=row["market_id"],
                    item_name=row["item_name"],
                    quantity=row["quantity"],
                    unit_price=row["unit_price"],
                    total_price=row["total_price"],
                    trader_name=row["trader_name"],
                    status=row["status"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    async def find_by_trading_id(self, trading_id: str) -> Optional[FoodTrading]:
        query = """
            SELECT id, trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at
            FROM schm04.tb_food_trading
            WHERE trading_id = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, trading_id)
            if row is None:
                return None
            return FoodTrading(
                id=row["id"],
                trading_id=row["trading_id"],
                market_id=row["market_id"],
                item_name=row["item_name"],
                quantity=row["quantity"],
                unit_price=row["unit_price"],
                total_price=row["total_price"],
                trader_name=row["trader_name"],
                status=row["status"],
                created_at=row["created_at"],
            )
