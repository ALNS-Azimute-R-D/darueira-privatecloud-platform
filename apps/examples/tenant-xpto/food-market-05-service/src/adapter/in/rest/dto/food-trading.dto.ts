import { ApiProperty } from '@nestjs/swagger';
import { FoodTrading } from '../../../../domain/food-trading.entity';

export class FoodTradingDto {
  @ApiProperty()
  id?: number;

  @ApiProperty()
  tradingId: string;

  @ApiProperty()
  marketId: string;

  @ApiProperty()
  itemName: string;

  @ApiProperty()
  quantity: number;

  @ApiProperty()
  unitPrice: number;

  @ApiProperty()
  totalPrice: number;

  @ApiProperty()
  traderName: string;

  @ApiProperty()
  status: string;

  @ApiProperty()
  createdAt: Date;

  static fromDomain(trading: FoodTrading): FoodTradingDto {
    const dto = new FoodTradingDto();
    dto.id = trading.id;
    dto.tradingId = trading.tradingId;
    dto.marketId = trading.marketId;
    dto.itemName = trading.itemName;
    dto.quantity = Number(trading.quantity);
    dto.unitPrice = Number(trading.unitPrice);
    dto.totalPrice = Number(trading.totalPrice);
    dto.traderName = trading.traderName;
    dto.status = trading.status;
    dto.createdAt = trading.createdAt;
    return dto;
  }
}
