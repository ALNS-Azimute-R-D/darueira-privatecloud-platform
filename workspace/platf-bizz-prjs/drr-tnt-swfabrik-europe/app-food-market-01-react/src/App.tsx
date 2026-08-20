import React, { useState, useEffect } from 'react';

interface FoodTrading {
  tradingId: string;
  itemName: string;
  quantity: number;
  totalPrice: number;
  traderName: string;
  status: string;
}

const baseUrl = typeof window !== 'undefined' && (
  window.location.hostname.includes('nip.io') ||
  window.location.hostname.includes('swfabrik') ||
  window.location.port === '80' ||
  window.location.port === ''
) ? '/api/food01/food-tradings' : 'http://localhost:8081/api/food-tradings';

const streamUrl = typeof window !== 'undefined' && (
  window.location.hostname.includes('nip.io') ||
  window.location.hostname.includes('swfabrik') ||
  window.location.port === '80' ||
  window.location.port === ''
) ? '/api/food01/food-tradings/stream' : 'http://localhost:8081/api/food-tradings/stream';

export function App() {
  const [items, setItems] = useState<FoodTrading[]>([]);
  const [liveMsg, setLiveMsg] = useState<string>('Connected');

  useEffect(() => {
    fetch(baseUrl)
      .then((res) => res.json())
      .then((data) => setItems(data || []))
      .catch(() => {});

    let es: EventSource | null = null;
    try {
      es = new EventSource(streamUrl);
      const onEvent = (e: MessageEvent) => {
        try {
          const item: FoodTrading = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
          if (item && item.tradingId) {
            setLiveMsg(`Live: ${item.tradingId}`);
            setItems((prev) => [item, ...prev.filter((p) => p.tradingId !== item.tradingId)]);
          }
        } catch {}
      };
      es.addEventListener('FOOD_TRADING_EVENT', onEvent);
      es.addEventListener('message', onEvent);
      es.onmessage = onEvent;
    } catch {}

    return () => {
      es?.close();
    };
  }, [baseUrl, streamUrl]);

  return (
    <div style={{ padding: '16px', background: '#0f172a', borderRadius: '12px', border: '1px solid #334155' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <h3 style={{ margin: 0, fontSize: '14px', color: '#38bdf8' }}>
          React MFE Widget (Java/Spring Boot 01 Stream)
        </h3>
        <span style={{ fontSize: '10px', color: '#10b981', background: 'rgba(16,185,129,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
          {liveMsg}
        </span>
      </div>
      <p style={{ margin: '0 0 12px 0', fontSize: '12px', color: '#94a3b8' }}>
        Isolated React 19 Microfrontend Component • Real-Time SSE Sync
      </p>
      <div style={{ fontSize: '11px', maxHeight: '160px', overflowY: 'auto' }}>
        {items.length === 0 ? (
          <div style={{ color: '#64748b' }}>No active trades</div>
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
