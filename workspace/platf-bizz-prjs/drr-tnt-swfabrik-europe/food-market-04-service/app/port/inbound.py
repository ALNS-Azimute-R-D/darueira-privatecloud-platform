from abc import ABC, abstractmethod
from typing import List, AsyncGenerator
from app.domain.models import FoodTrading, FoodTradingEvent, CreateFoodTradingCommand

class FoodTradingUseCase(ABC):
    @abstractmethod
    async def create_trading(self, cmd: CreateFoodTradingCommand) -> FoodTrading:
        pass

    @abstractmethod
    async def list_tradings(self) -> List[FoodTrading]:
        pass

    @abstractmethod
    async def subscribe_stream(self) -> AsyncGenerator[FoodTrading, None]:
        pass

    @abstractmethod
    async def process_incoming_event(self, event: FoodTradingEvent) -> None:
        pass
