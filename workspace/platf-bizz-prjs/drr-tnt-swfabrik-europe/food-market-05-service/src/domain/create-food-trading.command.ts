export class CreateFoodTradingCommand {
  itemName: string;
  quantity: number;
  unitPrice: number;
  traderName: string;

  constructor(partial: Partial<CreateFoodTradingCommand>) {
    Object.assign(this, partial);
  }
}
