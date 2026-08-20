import { Body, Controller, Get, Inject, Post, Sse } from '@nestjs/common';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { Observable } from 'rxjs';
import { CreateTradingDto } from './dto/create-trading.dto';
import { FoodTradingDto } from './dto/food-trading.dto';
import { FOOD_TRADING_USE_CASE, FoodTradingUseCasePort } from '../../../port/in/food-trading-use-case.port';
import { CreateFoodTradingCommand } from '../../../domain/create-food-trading.command';

@ApiTags('Food Tradings (NestJS)')
@Controller('api/food-tradings')
export class FoodTradingController {
  constructor(
    @Inject(FOOD_TRADING_USE_CASE)
    private readonly useCase: FoodTradingUseCasePort,
  ) {}

  @Post()
  @ApiOperation({ summary: 'F01.1: Create Food Trading in NestJS' })
  @ApiResponse({ status: 201, type: FoodTradingDto })
  async createTrading(@Body() dto: CreateTradingDto): Promise<FoodTradingDto> {
    const cmd = new CreateFoodTradingCommand({
      itemName: dto.itemName,
      quantity: dto.quantity,
      unitPrice: dto.unitPrice,
      traderName: dto.traderName,
    });
    const created = await this.useCase.createTrading(cmd);
    return FoodTradingDto.fromDomain(created);
  }

  @Get()
  @ApiOperation({ summary: 'F01.2: List Food Tradings from schema schm05' })
  @ApiResponse({ status: 200, type: [FoodTradingDto] })
  async listTradings(): Promise<FoodTradingDto[]> {
    const list = await this.useCase.listTradings();
    return list.map((item) => FoodTradingDto.fromDomain(item));
  }

  @Sse('stream')
  @ApiOperation({ summary: 'F01.3: Real-Time SSE Stream of Food Trading Events' })
  streamTradings(): Observable<any> {
    return this.useCase.subscribeStream();
  }
}
