import { Injectable, Logger } from '@nestjs/common';
import { Observable, Subject } from 'rxjs';
import { map } from 'rxjs/operators';
import { FoodTrading } from '../../../domain/food-trading.entity';
import { FoodTradingSseBroadcasterPort } from '../../../port/out/sse-broadcaster.port';

@Injectable()
export class SseBroadcasterAdapter implements FoodTradingSseBroadcasterPort {
  private readonly logger = new Logger(SseBroadcasterAdapter.name);
  private readonly subject = new Subject<FoodTrading>();

  stream(): Observable<any> {
    this.logger.log(`[NestJS 05] SSE client connected`);
    return this.subject.asObservable().pipe(
      map((trading) => ({
        type: 'FOOD_TRADING_EVENT',
        data: trading,
      })),
    );
  }

  broadcast(trading: FoodTrading): void {
    this.logger.log(`[NestJS 05] Broadcasting food trading via SSE: ${trading.tradingId}`);
    this.subject.next(trading);
  }
}
