import json
import logging
import aio_pika
from app.domain.models import FoodTradingEvent
from app.port.outbound import FoodTradingEventPublisherPort

logger = logging.getLogger(__name__)

class RabbitMQPublisher(FoodTradingEventPublisherPort):
    def __init__(self, amqp_url: str, topic_exchange: str):
        self.amqp_url = amqp_url
        self.topic_exchange = topic_exchange
        self.connection: aio_pika.RobustConnection | None = None
        self.channel: aio_pika.RobustChannel | None = None
        self.exchange: aio_pika.RobustExchange | None = None

    async def connect(self):
        try:
            self.connection = await aio_pika.connect_robust(self.amqp_url)
            self.channel = await self.connection.channel()
            self.exchange = await self.channel.declare_exchange(
                self.topic_exchange,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            logger.info(f"[Python 04] Connected RabbitMQ Publisher to exchange: {self.topic_exchange}")
        except Exception as e:
            logger.warning(f"[Python 04] Deferred RabbitMQ Publisher connection: {e}")

    async def publish_event(self, event: FoodTradingEvent) -> None:
        try:
            if not self.channel or self.channel.is_closed:
                await self.connect()

            payload = json.dumps({
                "eventId": event.event_id,
                "eventType": event.event_type,
                "tradingId": event.trading_id,
                "marketId": event.market_id,
                "itemName": event.item_name,
                "quantity": float(event.quantity),
                "unitPrice": float(event.unit_price),
                "totalPrice": float(event.total_price),
                "traderName": event.trader_name,
                "status": event.status,
                "timestamp": event.timestamp.isoformat(),
            }).encode()

            routing_key = f"foodtrading.created.{event.market_id.lower()}"
            message = aio_pika.Message(
                body=payload,
                content_type="application/json",
            )
            await self.exchange.publish(message, routing_key=routing_key)
            logger.info(f"[Python 04] Published event to RabbitMQ topic {self.topic_exchange} [{routing_key}]: {event.trading_id}")
        except Exception as e:
            logger.error(f"[Python 04] Failed to publish message to RabbitMQ: {e}")

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
