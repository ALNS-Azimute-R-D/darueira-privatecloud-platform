import { FoodTradingEvent } from '../../domain/food-trading.event';

export const EVENT_PUBLISHER_PORT = 'EVENT_PUBLISHER_PORT';

export interface FoodTradingEventPublisherPort {
  publishEvent(event: FoodTradingEvent): Promise<void>;
}
