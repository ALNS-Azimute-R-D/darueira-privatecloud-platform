import asyncio
from decimal import Decimal
from datetime import datetime
import json
from typing import List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.domain.models import CreateFoodTradingCommand, FoodTrading
from app.port.inbound import FoodTradingUseCase
from app.adapter.outbound.sse.broadcaster import SseBroadcaster

class CreateTradingRequest(BaseModel):
    itemName: str = Field(..., description="Food item name", min_length=1)
    quantity: Decimal = Field(..., description="Quantity", gt=0)
    unitPrice: Decimal = Field(..., description="Unit price", gt=0)
    traderName: str = Field(..., description="Trader name", min_length=1)

class FoodTradingResponse(BaseModel):
    id: int | None = None
    tradingId: str
    marketId: str
    itemName: str
    quantity: float
    unitPrice: float
    totalPrice: float
    traderName: str
    status: str
    createdAt: datetime

    @classmethod
    def from_domain(cls, t: FoodTrading) -> "FoodTradingResponse":
        return cls(
            id=t.id,
            tradingId=t.trading_id,
            marketId=t.market_id,
            itemName=t.item_name,
            quantity=float(t.quantity),
            unitPrice=float(t.unit_price),
            totalPrice=float(t.total_price),
            traderName=t.trader_name,
            status=t.status,
            createdAt=t.created_at,
        )

def get_router(use_case: FoodTradingUseCase, sse_broadcaster: SseBroadcaster) -> APIRouter:
    router = APIRouter(prefix="/api/food-tradings", tags=["Food Tradings (FastAPI)"])

    @router.post("", response_model=FoodTradingResponse, status_code=status.HTTP_201_CREATED, summary="Create Food Trading")
    async def create_trading(req: CreateTradingRequest):
        cmd = CreateFoodTradingCommand(
            item_name=req.itemName,
            quantity=req.quantity,
            unit_price=req.unitPrice,
            trader_name=req.traderName,
        )
        try:
            created = await use_case.create_trading(cmd)
            return FoodTradingResponse.from_domain(created)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("", response_model=List[FoodTradingResponse], summary="List Food Tradings")
    async def list_tradings():
        tradings = await use_case.list_tradings()
        return [FoodTradingResponse.from_domain(t) for t in tradings]

    @router.get("/stream", summary="Subscribe Food Tradings SSE Stream")
    async def stream_tradings():
        q = await sse_broadcaster.subscribe()

        async def event_generator():
            try:
                yield {
                    "event": "INIT",
                    "data": json.dumps({"message": "Connected to Food Trading Live SSE Stream (Service 04 - Python/FastAPI)"}),
                }
                while True:
                    trading: FoodTrading = await q.get()
                    resp = FoodTradingResponse.from_domain(trading)
                    yield {
                        "event": "FOOD_TRADING_EVENT",
                        "data": resp.model_dump_json(),
                    }
            except asyncio.CancelledError:
                pass
            finally:
                await sse_broadcaster.unsubscribe(q)

        return EventSourceResponse(event_generator())

    return router
