import { Inject, Injectable, Logger } from '@nestjs/common';
import { Observable } from 'rxjs';
import { FoodTrading } from '../domain/food-trading.entity';
import { FoodTradingEvent } from '../domain/food-trading.event';
import { CreateFoodTradingCommand } from '../domain/create-food-trading.command';
import { FoodTradingUseCasePort } from '../port/in/food-trading-use-case.port';
import { PERSISTENCE_PORT, FoodTradingPersistencePort } from '../port/out/persistence.port';
import { EVENT_PUBLISHER_PORT, FoodTradingEventPublisherPort } from '../port/out/event-publisher.port';
import { SSE_BROADCASTER_PORT, FoodTradingSseBroadcasterPort } from '../port/out/sse-broadcaster.port';

@Injectable()
export class FoodTradingApplicationService implements FoodTradingUseCasePort {
  private readonly logger = new Logger(FoodTradingApplicationService.name);
  private readonly marketId = process.env.APP_MARKET_ID || 'MKT-EU-05-NESTJS';

  constructor(
    @Inject(PERSISTENCE_PORT)
    private readonly persistence: FoodTradingPersistencePort,
    @Inject(EVENT_PUBLISHER_PORT)
    private readonly publisher: FoodTradingEventPublisherPort,
    @Inject(SSE_BROADCASTER_PORT)
    private readonly sseBroadcaster: FoodTradingSseBroadcasterPort,
  ) {}

  async createTrading(cmd: CreateFoodTradingCommand): Promise<FoodTrading> {
    this.logger.log(`[NestJS 05] Creating food trading: ${cmd.itemName} by ${cmd.traderName}`);

    const trading = new FoodTrading({
      marketId: this.marketId,
      itemName: cmd.itemName,
      quantity: Number(cmd.quantity),
      unitPrice: Number(cmd.unitPrice),
      traderName: cmd.traderName,
      status: 'CONFIRMED',
      createdAt: new Date(),
    });

    trading.validateAndCalculate();

    // 1. Persist to PostgreSQL (F02)
    const saved = await this.persistence.save(trading);

    // 2. Publish to RabbitMQ Topic (F03)
    const event = new FoodTradingEvent({
      tradingId: saved.tradingId,
      marketId: saved.marketId,
      itemName: saved.itemName,
      quantity: saved.quantity,
      unitPrice: saved.unitPrice,
      totalPrice: saved.totalPrice,
      traderName: saved.traderName,
      status: saved.status,
      timestamp: saved.createdAt.toISOString(),
    });

    await this.publisher.publishEvent(event);

    // 3. Broadcast to SSE (F01.3 / F04.2.3)
    this.sseBroadcaster.broadcast(saved);

    return saved;
  }

  async listTradings(): Promise<FoodTrading[]> {
    return this.persistence.findAll();
  }

  subscribeStream(): Observable<any> {
    return this.sseBroadcaster.stream();
  }

  async processIncomingEvent(event: FoodTradingEvent): Promise<void> {
    this.logger.log(`[NestJS 05] Consuming RabbitMQ message event: ${event.tradingId}`);

    if (event.quantity <= 0 || event.unitPrice <= 0) {
      this.logger.warn(`Discarding invalid event payload: ${event.tradingId}`);
      return;
    }

    const existing = await this.persistence.findByTradingId(event.tradingId);
    if (existing) {
      this.logger.log(`Trading ${event.tradingId} already exists in DB, skipping duplicate persist`);
      return;
    }

    const trading = new FoodTrading({
      tradingId: event.tradingId,
      marketId: event.marketId || this.marketId,
      itemName: event.itemName,
      quantity: Number(event.quantity),
      unitPrice: Number(event.unitPrice),
      traderName: event.traderName,
      status: 'CONFIRMED',
      createdAt: event.timestamp ? new Date(event.timestamp) : new Date(),
    });

    trading.validateAndCalculate();

    const saved = await this.persistence.save(trading);
    this.sseBroadcaster.broadcast(saved);
  }
}
