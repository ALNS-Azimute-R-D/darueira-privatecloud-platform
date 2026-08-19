export class FoodTradingEvent {
  eventId: string;
  eventType: string;
  tradingId: string;
  marketId: string;
  itemName: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  traderName: string;
  status: string;
  timestamp: string;

  constructor(partial: Partial<FoodTradingEvent>) {
    Object.assign(this, partial);
    if (!this.eventId) {
      this.eventId = Math.random().toString(36).substring(2, 15);
    }
    if (!this.eventType) {
      this.eventType = 'FOOD_TRADING_CREATED';
    }
    if (!this.timestamp) {
      this.timestamp = new Date().toISOString();
    }
  }
}
