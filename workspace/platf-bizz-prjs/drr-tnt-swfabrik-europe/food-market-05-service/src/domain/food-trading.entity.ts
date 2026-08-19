export class FoodTrading {
  id?: number;
  tradingId: string;
  marketId: string;
  itemName: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  traderName: string;
  status: string;
  createdAt: Date;

  constructor(partial: Partial<FoodTrading>) {
    Object.assign(this, partial);
    if (!this.status) {
      this.status = 'CONFIRMED';
    }
    if (!this.createdAt) {
      this.createdAt = new Date();
    }
  }

  validateAndCalculate(): void {
    if (!this.itemName || !this.itemName.trim()) {
      throw new Error('itemName must not be blank');
    }
    if (this.quantity <= 0) {
      throw new Error('quantity must be greater than zero');
    }
    if (this.unitPrice <= 0) {
      throw new Error('unitPrice must be greater than zero');
    }
    if (!this.traderName || !this.traderName.trim()) {
      throw new Error('traderName must not be blank');
    }
    if (!this.tradingId || !this.tradingId.trim()) {
      this.tradingId = `TRD-TS-${Math.random().toString(36).substring(2, 10).toUpperCase()}`;
    }
    this.totalPrice = Number((this.quantity * this.unitPrice).toFixed(2));
  }
}
