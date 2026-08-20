import asyncio
from contextlib import asynccontextmanager
import logging
import os
import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.service import FoodTradingService
from app.adapter.inbound.rest.router import get_router
from app.adapter.inbound.messaging.consumer import RabbitMQConsumer
from app.adapter.outbound.persistence.postgres import PostgresAdapter
from app.adapter.outbound.messaging.publisher import RabbitMQPublisher
from app.adapter.outbound.sse.broadcaster import SseBroadcaster

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("food-market-04-service")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://drr_tnt_svcs_admin:tenant_pg_secure_pass_2026@tenant-postgres.drr-tnt-swfabrik-europe-dev.svc.cluster.local:5432/drr_tnt_bizapps_db?sslmode=disable",
)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "drr_admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "darueira-admin123")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
if RABBITMQ_VHOST == "/":
    RABBITMQ_VHOST = ""
AMQP_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}"

MARKET_ID = os.getenv("APP_MARKET_ID", "MKT-EU-04-PYTHON")
TOPIC_EXCHANGE = os.getenv("APP_RABBITMQ_TOPIC", "marketplace.foodtrading.topic")
QUEUE_NAME = os.getenv("APP_RABBITMQ_QUEUE", "marketplace.foodtrading.queue04")

app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("==================================================================")
    logger.info("  Food Market 04 Service - Python / FastAPI / Hexagonal Architecture")
    logger.info("==================================================================")

    # 1. Connect to PostgreSQL
    clean_dsn = DATABASE_URL.replace("?sslmode=disable", "")
    pool = await asyncpg.create_pool(
        dsn=clean_dsn,
        min_size=2,
        max_size=10,
    )
    app_state["pool"] = pool
    logger.info("[Python 04] Connected to PostgreSQL (schema schm04)")

    # 2. Outbound Adapters
    pg_adapter = PostgresAdapter(pool)
    sse_broadcaster = SseBroadcaster()
    rmq_publisher = RabbitMQPublisher(AMQP_URL, TOPIC_EXCHANGE)
    await rmq_publisher.connect()

    # 3. Application Service
    service = FoodTradingService(
        persistence=pg_adapter,
        publisher=rmq_publisher,
        sse_broadcaster=sse_broadcaster,
        market_id=MARKET_ID,
    )

    # 4. Inbound Consumer
    consumer = RabbitMQConsumer(AMQP_URL, TOPIC_EXCHANGE, QUEUE_NAME, service)
    consumer_task = asyncio.create_task(consumer.start())

    # 5. Attach router
    router = get_router(service, sse_broadcaster)
    app.include_router(router)

    yield

    # Cleanup
    consumer.stop()
    consumer_task.cancel()
    await rmq_publisher.close()
    await pool.close()
    logger.info("[Python 04] Service stopped cleanly")

app = FastAPI(
    title="Food Market 04 Service API (Python / FastAPI)",
    version="1.0.0",
    description=f"Hexagonal Architecture REST API & SSE Stream for European Food Marketplaces in Python (Tenant: swfabrik-europe, Market: {MARKET_ID})",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz", tags=["Health"])
async def healthz():
    return {"status": "UP", "service": "food-market-04-service", "tech": "Python 3.12 / FastAPI"}
