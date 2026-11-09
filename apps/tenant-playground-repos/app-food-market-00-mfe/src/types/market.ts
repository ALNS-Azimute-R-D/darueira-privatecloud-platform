export interface FoodTrading {
  id?: number;
  tradingId: string;
  marketId: string;
  itemName: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  traderName: string;
  status: string;
  createdAt: string;
}

export interface CreateFoodTradingPayload {
  itemName: string;
  quantity: number;
  unitPrice: number;
  traderName: string;
}

export interface BackendServiceConfig {
  id: string;
  number: number;
  name: string;
  tech: string;
  techColor: string;
  iconBg: string;
  marketId: string;
  schema: string;
  port: number;
  endpoint: string;
  streamUrl: string;
  swaggerUrl: string;
  sampleItem: string;
  samplePrice: number;
  sampleTrader: string;
}
