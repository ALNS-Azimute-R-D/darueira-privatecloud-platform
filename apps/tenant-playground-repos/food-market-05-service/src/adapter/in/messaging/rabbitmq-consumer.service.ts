import { Inject, Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import * as amqp from 'amqplib';
import { FoodTradingEvent } from '../../../domain/food-trading.event';
import { FOOD_TRADING_USE_CASE, FoodTradingUseCasePort } from '../../../port/in/food-trading-use-case.port';

@Injectable()
export class RabbitmqConsumerService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RabbitmqConsumerService.name);
  private connection: any;
  private channel: any;
  private readonly topicExchange = process.env.APP_RABBITMQ_TOPIC || 'marketplace.foodtrading.topic';
  private readonly queueName = process.env.APP_RABBITMQ_QUEUE || 'marketplace.foodtrading.queue05';
  private running = true;

  constructor(
    @Inject(FOOD_TRADING_USE_CASE)
    private readonly useCase: FoodTradingUseCasePort,
  ) {}

  async onModuleInit() {
    this.startConsumer();
  }

  private async startConsumer() {
    while (this.running) {
      try {
        const host = process.env.RABBITMQ_HOST || 'message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local';
        const port = process.env.RABBITMQ_PORT || '5672';
        const user = process.env.RABBITMQ_USER || 'drr_admin';
        const pass = process.env.RABBITMQ_PASS || 'darueira-admin123';
        const vhost = process.env.RABBITMQ_VHOST === '/' ? '' : process.env.RABBITMQ_VHOST || '';
        const url = `amqp://${user}:${pass}@${host}:${port}/${vhost}`;

        this.connection = await amqp.connect(url);
        this.channel = await this.connection.createChannel();
        await this.channel.assertExchange(this.topicExchange, 'topic', { durable: true });
        await this.channel.assertQueue(this.queueName, { durable: true });
        await this.channel.bindQueue(this.queueName, this.topicExchange, '#');

        this.logger.log(`[NestJS 05] RabbitMQ Consumer listening on queue: ${this.queueName}`);

        await this.channel.consume(this.queueName, async (msg: any) => {
          if (msg !== null) {
            try {
              const data = JSON.parse(msg.content.toString());
              this.logger.log(`[NestJS 05] Consumed message from queue ${this.queueName}: ${data.tradingId}`);
              const event = new FoodTradingEvent(data);
              await this.useCase.processIncomingEvent(event);
              this.channel.ack(msg);
            } catch (err) {
              this.logger.error(`[NestJS 05] Failed to process consumed message: ${err.message}`);
              this.channel.nack(msg, false, false);
            }
          }
        });
        break;
      } catch (err) {
        this.logger.warn(`[NestJS 05] Consumer disconnected: ${err.message}. Retrying in 2s...`);
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
  }

  async onModuleDestroy() {
    this.running = false;
    try {
      await this.channel?.close();
      await this.connection?.close();
    } catch {}
  }
}
