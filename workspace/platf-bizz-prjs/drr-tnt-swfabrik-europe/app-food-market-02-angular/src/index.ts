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

    fetch('http://localhost:8082/api/food-tradings')
      .then((res) => res.json())
      .then((data) => {
        const listDiv = this.querySelector('#angular-trading-list');
        if (!listDiv) return;
        if (!data || data.length === 0) {
          listDiv.innerHTML = '<div>No active trades</div>';
          return;
        }
        listDiv.innerHTML = data
          .map(
            (i: any) =>
              `<div style="padding: 4px 0; border-bottom: 1px solid #1e293b;">
                <strong style="color: #38bdf8;">${i.tradingId}</strong>: ${i.itemName} — €${i.totalPrice} (${i.traderName})
              </div>`
          )
          .join('');
      })
      .catch(() => {
        const listDiv = this.querySelector('#angular-trading-list');
        if (listDiv) listDiv.innerHTML = '<div>Offline / Waiting for Service 02</div>';
      });
  }
}

customElements.define('food-market-angular-widget', FoodMarketAngularWidget);
