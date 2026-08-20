import { Observable } from 'rxjs';
import { FoodTrading } from '../../domain/food-trading.entity';
import { CreateFoodTradingCommand } from '../../domain/create-food-trading.command';
import { FoodTradingEvent } from '../../domain/food-trading.event';

export const FOOD_TRADING_USE_CASE = 'FOOD_TRADING_USE_CASE';

export interface FoodTradingUseCasePort {
  createTrading(cmd: CreateFoodTradingCommand): Promise<FoodTrading>;
  listTradings(): Promise<FoodTrading[]>;
  subscribeStream(): Observable<MessageEvent | any>;
  processIncomingEvent(event: FoodTradingEvent): Promise<void>;
}
