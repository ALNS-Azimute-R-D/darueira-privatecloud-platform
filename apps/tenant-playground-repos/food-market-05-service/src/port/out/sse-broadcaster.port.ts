import { Observable } from 'rxjs';
import { FoodTrading } from '../../domain/food-trading.entity';

export const SSE_BROADCASTER_PORT = 'SSE_BROADCASTER_PORT';

export interface FoodTradingSseBroadcasterPort {
  stream(): Observable<any>;
  broadcast(trading: FoodTrading): void;
}
