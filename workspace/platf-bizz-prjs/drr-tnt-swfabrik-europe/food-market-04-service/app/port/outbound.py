from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models import FoodTrading, FoodTradingEvent

class FoodTradingPersistencePort(ABC):
    @abstractmethod
    async def save(self, trading: FoodTrading) -> FoodTrading:
        pass

    @abstractmethod
    async def find_all(self) -> List[FoodTrading]:
        pass

    @abstractmethod
    async def find_by_trading_id(self, trading_id: str) -> Optional[FoodTrading]:
        pass

class FoodTradingEventPublisherPort(ABC):
    @abstractmethod
    async def publish_event(self, event: FoodTradingEvent) -> None:
        pass

class FoodTradingSseBroadcasterPort(ABC):
    @abstractmethod
    async def broadcast(self, trading: FoodTrading) -> None:
        pass
