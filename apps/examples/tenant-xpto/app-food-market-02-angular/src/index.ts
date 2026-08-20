// Angular-style Custom Element Component for Food Market Service 02 (Kotlin/Quarkus)
class FoodMarketAngularWidget extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div style="padding: 16px; background: #0f172a; border-radius: 12px; border: 1px solid #334155; font-family: sans-serif;">
        <h3 style="margin: 0 0 8px 0; font-size: 14px; color: #a78bfa;">
          Angular MFE Widget (Kotlin/Quarkus 02 Stream)
        </h3>
        <p style="margin: 0 0 12px 0; font-size: 12px; color: #94a3b8;">
          Angular Custom Element Microfrontend
        </p>
        <div id="angular-trading-list" style="font-size: 11px; max-height: 160px; overflow-y: auto;">
          Loading trading items...
        </div>
      </div>
    `;

    const isGateway = typeof window !== 'undefined' && (
      window.location.hostname.includes('nip.io') ||
      window.location.hostname.includes('swfabrik') ||
      window.location.port === '80' ||
      window.location.port === ''
    );

    const baseUrl = isGateway ? '/api/food02/food-tradings' : 'http://localhost:8082/api/food-tradings';
    const streamUrl = isGateway ? '/api/food02/food-tradings/stream' : 'http://localhost:8082/api/food-tradings/stream';

    let tradings: any[] = [];

    const renderList = () => {
      const listDiv = this.querySelector('#angular-trading-list');
      if (!listDiv) return;
      if (tradings.length === 0) {
        listDiv.innerHTML = '<div style="color: #64748b;">No active trades</div>';
        return;
      }
      listDiv.innerHTML = tradings
        .map(
          (i: any) =>
            `<div style="padding: 4px 0; border-bottom: 1px solid #1e293b;">
              <strong style="color: #38bdf8;">${i.tradingId}</strong>: ${i.itemName} — €${Number(i.totalPrice).toFixed(2)} (${i.traderName})
            </div>`
        )
        .join('');
    };

    fetch(baseUrl)
      .then((res) => res.json())
      .then((data) => {
        tradings = data || [];
        renderList();
      })
      .catch(() => {
        const listDiv = this.querySelector('#angular-trading-list');
        if (listDiv) listDiv.innerHTML = '<div style="color: #f43f5e;">Offline / Waiting for Service 02</div>';
      });

    try {
      const es = new EventSource(streamUrl);
      const onMsg = (e: MessageEvent) => {
        try {
          const item = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
          if (item && item.tradingId) {
            tradings = [item, ...tradings.filter((t) => t.tradingId !== item.tradingId)];
            renderList();
          }
        } catch {}
      };
      es.addEventListener('FOOD_TRADING_EVENT', onMsg);
      es.addEventListener('message', onMsg);
      es.onmessage = onMsg;
    } catch {}
  }
}

customElements.define('food-market-angular-widget', FoodMarketAngularWidget);
