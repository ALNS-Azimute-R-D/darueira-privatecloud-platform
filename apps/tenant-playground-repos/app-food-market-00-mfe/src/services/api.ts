import { CreateFoodTradingPayload, FoodTrading } from '../types/market';

export async function fetchTradings(endpoint: string): Promise<FoodTrading[]> {
  const resp = await fetch(endpoint);
  if (!resp.ok) {
    throw new Error(`Failed to fetch tradings: ${resp.statusText}`);
  }
  return resp.json();
}

export async function createTrading(endpoint: string, payload: CreateFoodTradingPayload): Promise<FoodTrading> {
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({}));
    throw new Error(errorData.error || errorData.detail || `Failed with status ${resp.status}`);
  }
  return resp.json();
}
