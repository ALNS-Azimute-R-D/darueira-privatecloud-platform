import React, { useState, useEffect } from 'react';

interface FoodTrading {
  tradingId: string;
  itemName: string;
  quantity: number;
  totalPrice: number;
  traderName: string;
  status: string;
}

export function App() {
  const [items, setItems] = useState<FoodTrading[]>([]);

  useEffect(() => {
    fetch('http://localhost:8081/api/food-tradings')
      .then((res) => res.json())
      .then((data) => setItems(data || []))
      .catch(() => {});
  }, []);

  return (
    <div style={{ padding: '16px', background: '#0f172a', borderRadius: '12px', border: '1px solid #334155' }}>
      <h3 style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#38bdf8' }}>
        React MFE Widget (Java/Spring Boot 01 Stream)
      </h3>
      <p style={{ margin: '0 0 12px 0', fontSize: '12px', color: '#94a3b8' }}>
        Isolated React 19 Microfrontend Component
      </p>
      <div style={{ fontSize: '11px', maxHeight: '160px', overflowY: 'auto' }}>
        {items.length === 0 ? (
          <div>No active trades</div>
        ) : (
          items.map((i) => (
            <div key={i.tradingId} style={{ padding: '4px 0', borderBottom: '1px solid #1e293b' }}>
              <strong style={{ color: '#f59e0b' }}>{i.tradingId}</strong>: {i.itemName} — €{i.totalPrice} ({i.traderName})
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default App;
