import asyncio
import logging
from typing import Set
from app.domain.models import FoodTrading
from app.port.outbound import FoodTradingSseBroadcasterPort

logger = logging.getLogger(__name__)

class SseBroadcaster(FoodTradingSseBroadcasterPort):
    def __init__(self):
        self.subscribers: Set[asyncio.Queue] = set()

    async def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self.subscribers.add(q)
        logger.info(f"[Python 04] SSE client connected (Total active: {len(self.subscribers)})")
        return q

    async def unsubscribe(self, q: asyncio.Queue):
        if q in self.subscribers:
            self.subscribers.remove(q)
            logger.info(f"[Python 04] SSE client disconnected (Total active: {len(self.subscribers)})")

    async def broadcast(self, trading: FoodTrading) -> None:
        logger.info(f"[Python 04] Broadcasting food trading via SSE to {len(self.subscribers)} active clients: {trading.trading_id}")
        for q in list(self.subscribers):
            try:
                q.put_nowait(trading)
            except asyncio.QueueFull:
                logger.warning("[Python 04] Dropped SSE message for slow client")
