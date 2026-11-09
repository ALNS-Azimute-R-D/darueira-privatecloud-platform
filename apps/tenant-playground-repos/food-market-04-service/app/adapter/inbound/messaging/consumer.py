import asyncio
from datetime import datetime
from decimal import Decimal
import json
import logging
import aio_pika
from app.domain.models import FoodTradingEvent
from app.port.inbound import FoodTradingUseCase

logger = logging.getLogger(__name__)

class RabbitMQConsumer:
    def __init__(self, amqp_url: str, topic_exchange: str, queue_name: str, use_case: FoodTradingUseCase):
        self.amqp_url = amqp_url
        self.topic_exchange = topic_exchange
        self.queue_name = queue_name
        self.use_case = use_case
        self.running = True

    async def start(self):
        while self.running:
            try:
                connection = await aio_pika.connect_robust(self.amqp_url)
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)
                exchange = await channel.declare_exchange(self.topic_exchange, aio_pika.ExchangeType.TOPIC, durable=True)
                queue = await channel.declare_queue(self.queue_name, durable=True)
                await queue.bind(exchange, routing_key="#")

                logger.info(f"[Python 04] RabbitMQ Consumer listening on queue: {self.queue_name}")

                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        async with message.process():
                            try:
                                data = json.loads(message.body.decode())
                                logger.info(f"[Python 04] Consumed message from queue {self.queue_name}: {data.get('tradingId')}")
                                
                                ts_str = data.get("timestamp")
                                ts = datetime.fromisoformat(ts_str) if ts_str else datetime.utcnow()

                                event = FoodTradingEvent(
                                    event_id=data.get("eventId", ""),
                                    event_type=data.get("eventType", "FOOD_TRADING_CREATED"),
                                    trading_id=data.get("tradingId", ""),
                                    market_id=data.get("marketId", ""),
                                    item_name=data.get("itemName", ""),
                                    quantity=Decimal(str(data.get("quantity", 0))),
                                    unit_price=Decimal(str(data.get("unitPrice", 0))),
                                    total_price=Decimal(str(data.get("totalPrice", 0))),
                                    trader_name=data.get("traderName", ""),
                                    status=data.get("status", "CONFIRMED"),
                                    timestamp=ts,
                                )
                                await self.use_case.process_incoming_event(event)
                            except Exception as e:
                                logger.error(f"[Python 04] Failed to process message: {e}")
            except Exception as e:
                logger.warning(f"[Python 04] Consumer disconnected: {e}. Retrying in 2s...")
                await asyncio.sleep(2)

    def stop(self):
        self.running = False
