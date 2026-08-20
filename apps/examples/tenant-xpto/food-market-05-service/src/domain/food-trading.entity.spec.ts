import { FoodTrading } from './food-trading.entity';

describe('FoodTrading Entity (TypeScript)', () => {
  it('should validate and calculate total price properly', () => {
    const trading = new FoodTrading({
      marketId: 'MKT-EU-05-NESTJS',
      itemName: 'Belgian Chocolate Wafers 500g',
      quantity: 50,
      unitPrice: 4.5,
      traderName: 'Brussels Confectionery SA',
    });

    trading.validateAndCalculate();

    expect(trading.tradingId).toBeDefined();
    expect(trading.tradingId.startsWith('TRD-TS-')).toBe(true);
    expect(trading.totalPrice).toBe(225.0);
    expect(trading.status).toBe('CONFIRMED');
  });

  it('should throw error when quantity is invalid', () => {
    const trading = new FoodTrading({
      marketId: 'MKT-EU-05-NESTJS',
      itemName: 'Belgian Chocolate Wafers 500g',
      quantity: -5,
      unitPrice: 4.5,
      traderName: 'Brussels Confectionery SA',
    });

    expect(() => trading.validateAndCalculate()).toThrow('quantity must be greater than zero');
  });
});
