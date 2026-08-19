import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import * as amqp from 'amqplib';
import { FoodTradingEvent } from '../../../domain/food-trading.event';
import { FoodTradingEventPublisherPort } from '../../../port/out/event-publisher.port';

@Injectable()
export class RabbitmqPublisherAdapter implements FoodTradingEventPublisherPort, OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RabbitmqPublisherAdapter.name);
  private connection: any;
  private channel: any;
  private readonly topicExchange = process.env.APP_RABBITMQ_TOPIC || 'marketplace.foodtrading.topic';

  async onModuleInit() {
    await this.connect();
  }

  private async connect() {
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
      this.logger.log(`[NestJS 05] Connected RabbitMQ Publisher to exchange: ${this.topicExchange}`);
    } catch (e) {
      this.logger.warn(`[NestJS 05] Deferred RabbitMQ Publisher connection: ${e.message}`);
    }
  }

  async publishEvent(event: FoodTradingEvent): Promise<void> {
    try {
      if (!this.channel) {
        await this.connect();
      }
      const routingKey = `foodtrading.created.${event.marketId.toLowerCase()}`;
      const payload = Buffer.from(JSON.stringify(event));
      this.channel.publish(this.topicExchange, routingKey, payload, {
        contentType: 'application/json',
        timestamp: Date.now(),
      });
      this.logger.log(`[NestJS 05] Published event to RabbitMQ topic ${this.topicExchange} [${routingKey}]: ${event.tradingId}`);
    } catch (e) {
      this.logger.error(`[NestJS 05] Failed to publish message: ${e.message}`);
    }
  }

  async onModuleDestroy() {
    try {
      await this.channel?.close();
      await this.connection?.close();
    } catch {}
  }
}
