import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.enableCors({ origin: '*' });
  app.useGlobalPipes(new ValidationPipe({ transform: true }));

  const marketId = process.env.APP_MARKET_ID || 'MKT-EU-05-NESTJS';
  const port = process.env.PORT || 8085;

  const config = new DocumentBuilder()
    .setTitle('Food Market 05 Service API (TypeScript / NestJS)')
    .setDescription(
      `Hexagonal Architecture REST API & SSE Stream for European Food Marketplaces in TypeScript (Tenant: swfabrik-europe, Market: ${marketId})`,
    )
    .setVersion('1.0.0')
    .addTag('Food Tradings (NestJS)')
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('swagger-ui', app, document);

  // Health endpoint
  const httpAdapter = app.getHttpAdapter();
  httpAdapter.get('/healthz', (req, res) => {
    res.json({ status: 'UP', service: 'food-market-05-service', tech: 'TypeScript / NestJS' });
  });
  httpAdapter.get('/v3/api-docs', (req, res) => {
    res.json(document);
  });

  await app.listen(port, '0.0.0.0');
  console.log(`[NestJS 05] Application listening on http://0.0.0.0:${port}`);
}
bootstrap();
