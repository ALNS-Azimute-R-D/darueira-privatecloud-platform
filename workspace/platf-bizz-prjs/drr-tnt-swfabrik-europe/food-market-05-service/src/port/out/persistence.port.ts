import { FoodTrading } from '../../domain/food-trading.entity';

export const PERSISTENCE_PORT = 'PERSISTENCE_PORT';

export interface FoodTradingPersistencePort {
  save(trading: FoodTrading): Promise<FoodTrading>;
  findAll(): Promise<FoodTrading[]>;
  findByTradingId(tradingId: string): Promise<FoodTrading | null>;
}
