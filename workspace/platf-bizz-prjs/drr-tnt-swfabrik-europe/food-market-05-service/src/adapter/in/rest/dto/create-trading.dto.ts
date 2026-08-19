import { ApiProperty } from '@nestjs/swagger';
import { IsNotEmpty, IsNumber, IsPositive, IsString } from 'class-validator';

export class CreateTradingDto {
  @ApiProperty({ description: 'Name of the food trading product', example: 'Belgian Dark Chocolate Couverture 10kg' })
  @IsString()
  @IsNotEmpty()
  itemName: string;

  @ApiProperty({ description: 'Trading quantity in kilograms or units', example: 20.0 })
  @IsNumber()
  @IsPositive()
  quantity: number;

  @ApiProperty({ description: 'Unit price in EUR', example: 55.0 })
  @IsNumber()
  @IsPositive()
  unitPrice: number;

  @ApiProperty({ description: 'Trader or cooperative name', example: 'Antwerp Cacao Trading NV' })
  @IsString()
  @IsNotEmpty()
  traderName: string;
}
