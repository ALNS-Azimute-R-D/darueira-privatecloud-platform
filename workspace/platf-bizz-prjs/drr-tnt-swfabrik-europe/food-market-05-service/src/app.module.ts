import { Module } from '@nestjs/common';
import { FoodTradingController } from './adapter/in/rest/food-trading.controller';
import { FoodTradingApplicationService } from './application/food-trading.service';
import { FOOD_TRADING_USE_CASE } from './port/in/food-trading-use-case.port';
import { PERSISTENCE_PORT } from './port/out/persistence.port';
import { PostgresFoodTradingAdapter } from './adapter/out/persistence/postgres-food-trading.adapter';
import { EVENT_PUBLISHER_PORT } from './port/out/event-publisher.port';
import { RabbitmqPublisherAdapter } from './adapter/out/messaging/rabbitmq-publisher.adapter';
import { SSE_BROADCASTER_PORT } from './port/out/sse-broadcaster.port';
import { SseBroadcasterAdapter } from './adapter/out/sse/sse-broadcaster.adapter';
import { RabbitmqConsumerService } from './adapter/in/messaging/rabbitmq-consumer.service';

@Module({
  imports: [],
  controllers: [FoodTradingController],
  providers: [
    FoodTradingApplicationService,
    {
      provide: FOOD_TRADING_USE_CASE,
      useExisting: FoodTradingApplicationService,
    },
    {
      provide: PERSISTENCE_PORT,
      useClass: PostgresFoodTradingAdapter,
    },
    {
      provide: EVENT_PUBLISHER_PORT,
      useClass: RabbitmqPublisherAdapter,
    },
    {
      provide: SSE_BROADCASTER_PORT,
      useClass: SseBroadcasterAdapter,
    },
    RabbitmqConsumerService,
  ],
})
export class AppModule {}
