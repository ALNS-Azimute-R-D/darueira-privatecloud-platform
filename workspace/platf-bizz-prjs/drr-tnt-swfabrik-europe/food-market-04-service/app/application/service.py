import logging
from decimal import Decimal
from typing import List, AsyncGenerator
from app.domain.models import FoodTrading, FoodTradingEvent, CreateFoodTradingCommand
from app.port.inbound import FoodTradingUseCase
from app.port.outbound import FoodTradingPersistencePort, FoodTradingEventPublisherPort, FoodTradingSseBroadcasterPort

logger = logging.getLogger(__name__)

class FoodTradingService(FoodTradingUseCase):
    def __init__(
        self,
        persistence: FoodTradingPersistencePort,
        publisher: FoodTradingEventPublisherPort,
        sse_broadcaster: FoodTradingSseBroadcasterPort,
        market_id: str,
    ):
        self.persistence = persistence
        self.publisher = publisher
        self.sse_broadcaster = sse_broadcaster
        self.market_id = market_id

    async def create_trading(self, cmd: CreateFoodTradingCommand) -> FoodTrading:
        logger.info(f"[Python 04] Creating food trading: {cmd.item_name} by {cmd.trader_name}")
        trading = FoodTrading(
            market_id=self.market_id,
            item_name=cmd.item_name,
            quantity=cmd.quantity,
            unit_price=cmd.unit_price,
            trader_name=cmd.trader_name,
        )
        trading.validate_and_calculate()

        # 1. Persist (F02)
        saved = await self.persistence.save(trading)

        # 2. Publish to RabbitMQ Topic (F03)
        event = FoodTradingEvent(
            trading_id=saved.trading_id,
            market_id=saved.market_id,
            item_name=saved.item_name,
            quantity=saved.quantity,
            unit_price=saved.unit_price,
            total_price=saved.total_price,
            trader_name=saved.trader_name,
            status=saved.status,
            timestamp=saved.created_at,
        )
        await self.publisher.publish_event(event)

        # 3. Broadcast to SSE (F01.3 / F04.2.3)
        await self.sse_broadcaster.broadcast(saved)

        return saved

    async def list_tradings(self) -> List[FoodTrading]:
        return await self.persistence.find_all()

    async def subscribe_stream(self) -> AsyncGenerator[FoodTrading, None]:
        # Generator handled by SSE Broadcaster queue
        pass

    async def process_incoming_event(self, event: FoodTradingEvent) -> None:
        logger.info(f"[Python 04] Consuming RabbitMQ message event: {event.trading_id}")

        if event.quantity <= Decimal("0.00") or event.unit_price <= Decimal("0.00"):
            logger.warning(f"Discarding invalid event: {event.trading_id}")
            return

        existing = await self.persistence.find_by_trading_id(event.trading_id)
        if existing is not None:
            logger.info(f"Trading {event.trading_id} already exists in DB, skipping duplicate persist")
            return

        trading = FoodTrading(
            trading_id=event.trading_id,
            market_id=event.market_id or self.market_id,
            item_name=event.item_name,
            quantity=event.quantity,
            unit_price=event.unit_price,
            trader_name=event.trader_name,
            status="CONFIRMED",
            created_at=event.timestamp,
        )
        trading.validate_and_calculate()

        saved = await self.persistence.save(trading)
        await self.sse_broadcaster.broadcast(saved)
