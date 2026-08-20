import React, { useState, useEffect } from 'react';
import { BackendServiceConfig, FoodTrading } from '../types/market';
import { fetchTradings, createTrading } from '../services/api';
import { 
  Send, 
  Activity, 
  ExternalLink, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Radio, 
  TrendingUp, 
  Package, 
  DollarSign, 
  User 
} from 'lucide-react';

interface BackendCardProps {
  config: BackendServiceConfig;
  onTradingAdded?: () => void;
  onStreamStateChange?: (active: boolean) => void;
}

export const BackendCard: React.FC<BackendCardProps> = ({ config, onTradingAdded, onStreamStateChange }) => {
  const [tradings, setTradings] = useState<FoodTrading[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [sseConnected, setSseConnected] = useState<boolean>(false);
  const [latestSseEvent, setLatestSseEvent] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form State
  const [itemName, setItemName] = useState<string>(config.sampleItem);
  const [quantity, setQuantity] = useState<number>(25);
  const [unitPrice, setUnitPrice] = useState<number>(config.samplePrice);
  const [traderName, setTraderName] = useState<string>(config.sampleTrader);

  const loadData = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const data = await fetchTradings(config.endpoint);
      setTradings(data || []);
      if (onTradingAdded) onTradingAdded();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to connect to microservice');
    } finally {
      setLoading(false);
    }
  };

  // Connect SSE with Auto-Reconnect & Heartbeat Handling
  useEffect(() => {
    let eventSource: EventSource | null = null;
    let reconnectTimeout: any = null;
    let isSubscribed = true;

    const connect = () => {
      if (!isSubscribed) return;
      try {
        eventSource = new EventSource(config.streamUrl);

        eventSource.onopen = () => {
          if (!isSubscribed) return;
          setSseConnected(true);
          if (onStreamStateChange) onStreamStateChange(true);
        };

        const handleIncomingEvent = (rawData: any) => {
          try {
            if (!rawData) return;
            // Ignore heartbeats / pings
            if (rawData === 'heartbeat' || rawData === 'ping' || rawData === ': ping') return;

            let item: FoodTrading | null = null;
            if (typeof rawData === 'string') {
              if (rawData.trim().startsWith('{')) {
                item = JSON.parse(rawData);
              } else {
                return;
              }
            } else if (typeof rawData === 'object') {
              item = rawData;
            }

            if (item) {
              const normalizedItem: FoodTrading = {
                id: (item as any).id || (item as any).Id,
                tradingId: (item as any).tradingId || (item as any).TradingId,
                marketId: (item as any).marketId || (item as any).MarketId,
                itemName: (item as any).itemName || (item as any).ItemName,
                quantity: Number((item as any).quantity ?? (item as any).Quantity ?? 0),
                unitPrice: Number((item as any).unitPrice ?? (item as any).UnitPrice ?? 0),
                totalPrice: Number((item as any).totalPrice ?? (item as any).TotalPrice ?? 0),
                traderName: (item as any).traderName || (item as any).TraderName || '',
                status: (item as any).status || (item as any).Status || 'CONFIRMED',
                createdAt: (item as any).createdAt || (item as any).CreatedAt || new Date().toISOString(),
              };

              if (normalizedItem.tradingId && normalizedItem.tradingId !== 'INIT' && normalizedItem.tradingId !== 'PING') {
                setLatestSseEvent(`Live: ${normalizedItem.tradingId} (${normalizedItem.itemName || 'Trading'})`);
                setTradings((prev) => {
                  const existingIdx = prev.findIndex((p) => p.tradingId === normalizedItem.tradingId);
                  if (existingIdx >= 0) {
                    const updated = [...prev];
                    updated[existingIdx] = { ...updated[existingIdx], ...normalizedItem };
                    return updated;
                  }
                  return [normalizedItem, ...prev];
                });
                if (onTradingAdded) onTradingAdded();
              }
            }
          } catch (err) {
            console.error("Error processing SSE message:", err);
          }
        };

        eventSource.addEventListener('INIT', (e: MessageEvent) => {
          if (isSubscribed) {
            setLatestSseEvent(`Connected`);
          }
        });

        eventSource.addEventListener('FOOD_TRADING_EVENT', (e: MessageEvent) => {
          handleIncomingEvent(e.data);
        });

        eventSource.addEventListener('message', (e: MessageEvent) => {
          handleIncomingEvent(e.data);
        });

        eventSource.onmessage = (e: MessageEvent) => {
          handleIncomingEvent(e.data);
        };

        eventSource.onerror = () => {
          if (!isSubscribed) return;
          setSseConnected(false);
          if (onStreamStateChange) onStreamStateChange(false);
          eventSource?.close();
          // Auto-reconnect after 3 seconds
          reconnectTimeout = setTimeout(() => {
            if (isSubscribed) connect();
          }, 3000);
        };
      } catch {
        if (!isSubscribed) return;
        setSseConnected(false);
        if (onStreamStateChange) onStreamStateChange(false);
        reconnectTimeout = setTimeout(() => {
          if (isSubscribed) connect();
        }, 3000);
      }
    };

    connect();

    // Initial data load
    loadData();

    // Periodic safety poll every 15s to guarantee 100% data consistency
    const pollInterval = setInterval(() => {
      if (isSubscribed) loadData();
    }, 15000);

    return () => {
      isSubscribed = false;
      if (eventSource) {
        eventSource.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      clearInterval(pollInterval);
    };
  }, [config.endpoint, config.streamUrl]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemName || quantity <= 0 || unitPrice <= 0 || !traderName) {
      setErrorMsg('Please fill all fields with valid numbers');
      return;
    }

    try {
      setSubmitting(true);
      setErrorMsg(null);
      const created = await createTrading(config.endpoint, {
        itemName,
        quantity: Number(quantity),
        unitPrice: Number(unitPrice),
        traderName,
      });

      setTradings((prev) => {
        if (prev.some((p) => p.tradingId === created.tradingId)) return prev;
        return [created, ...prev];
      });

      setLatestSseEvent(`Created: ${created.tradingId}`);
      if (onTradingAdded) onTradingAdded();
    } catch (err: any) {
      setErrorMsg(err.message || 'Submission error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl flex flex-col overflow-hidden hover:border-slate-700 transition-all duration-200">
      {/* Card Header */}
      <div className="p-4 border-b border-slate-800/80 bg-slate-900 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm shadow-md ${config.iconBg} text-white`}>
            0{config.number}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="font-semibold text-sm text-white">{config.name}</h3>
              <span className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider ${config.techColor}`}>
                {config.tech}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Port: <span className="text-slate-300 font-mono">:{config.port}</span> • Schema: <span className="text-slate-300 font-mono">{config.schema}</span> • Market: <span className="text-slate-300 font-mono">{config.marketId}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* SSE Status Indicator */}
          <div 
            className={`flex items-center space-x-1.5 px-2 py-1 rounded text-[11px] border font-medium ${
              sseConnected
                ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
                : 'bg-rose-950/40 text-rose-400 border-rose-800/60'
            }`}
            title={sseConnected ? 'SSE Live Stream Connected' : 'SSE Disconnected'}
          >
            <Radio className={`w-3 h-3 ${sseConnected ? 'animate-pulse text-emerald-400' : 'text-rose-400'}`} />
            <span>{sseConnected ? 'SSE Live' : 'Offline'}</span>
          </div>

          {/* Swagger link */}
          <a
            href={config.swaggerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded border border-slate-700 transition"
            title="Open Swagger / OpenAPI Docs"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Real-Time Event Banner */}
      {latestSseEvent && (
        <div className="bg-blue-950/40 border-b border-blue-900/40 px-4 py-1.5 flex items-center justify-between text-xs text-blue-300">
          <div className="flex items-center space-x-2 truncate">
            <Activity className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span className="truncate font-mono text-[11px]">{latestSseEvent}</span>
          </div>
          <span className="text-[10px] text-blue-400/80 uppercase font-semibold shrink-0">Live Event</span>
        </div>
      )}

      {/* Error Message */}
      {errorMsg && (
        <div className="bg-rose-950/40 border-b border-rose-900/40 px-4 py-2 flex items-center space-x-2 text-xs text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span className="truncate">{errorMsg}</span>
        </div>
      )}

      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Create Food Trading Form (F01.1) */}
        <form onSubmit={handleSubmit} className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 space-y-2.5">
          <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
            <span>Create Food Trading Order</span>
            <span className="text-[10px] text-slate-500 font-normal">POST /api/food-tradings</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] text-slate-400 mb-0.5">Item Name</label>
              <input
                type="text"
                value={itemName}
                onChange={(e) => setItemName(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
                placeholder="e.g. Olive Oil 5L"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 mb-0.5">Trader / Supplier</label>
              <input
                type="text"
                value={traderName}
                onChange={(e) => setTraderName(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
                placeholder="e.g. Madrid Foods"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 mb-0.5">Quantity (Units / Kg)</label>
              <input
                type="number"
                step="any"
                value={quantity}
                onChange={(e) => setQuantity(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
                placeholder="Quantity"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 mb-0.5">Unit Price (€)</label>
              <input
                type="number"
                step="any"
                value={unitPrice}
                onChange={(e) => setUnitPrice(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
                placeholder="Unit Price"
                required
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <div className="text-xs text-slate-400">
              Total: <span className="font-semibold text-white">€{(quantity * unitPrice).toFixed(2)}</span>
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-xs font-medium flex items-center space-x-1.5 transition shadow"
            >
              {submitting ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                <Send className="w-3 h-3" />
              )}
              <span>Publish & Trade</span>
            </button>
          </div>
        </form>

        {/* Live Data Grid (F01.2) */}
        <div className="flex-1 flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-xs font-semibold text-slate-300">Live Trades in {config.schema}</span>
              <span className="px-1.5 py-0.2 bg-slate-800 text-slate-400 text-[10px] rounded-full">
                {tradings.length}
              </span>
            </div>
            <button
              onClick={loadData}
              disabled={loading}
              className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition"
              title="Refresh Data"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto max-h-48 border border-slate-800/80 rounded-lg bg-slate-950/40">
            {tradings.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-500">
                No trading records yet. Submit a new order above!
              </div>
            ) : (
              <table className="w-full text-left text-[11px]">
                <thead className="bg-slate-900/90 sticky top-0 text-slate-400 border-b border-slate-800 text-[10px] uppercase">
                  <tr>
                    <th className="py-1.5 px-2">Order ID</th>
                    <th className="py-1.5 px-2">Item</th>
                    <th className="py-1.5 px-2">Qty</th>
                    <th className="py-1.5 px-2">Total (€)</th>
                    <th className="py-1.5 px-2">Trader</th>
                    <th className="py-1.5 px-2 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {tradings.map((t, idx) => (
                    <tr key={t.tradingId || idx} className="hover:bg-slate-800/40 transition">
                      <td className="py-1.5 px-2 text-blue-400 font-semibold">{t.tradingId}</td>
                      <td className="py-1.5 px-2 text-slate-200 font-sans">{t.itemName}</td>
                      <td className="py-1.5 px-2 text-slate-400">{t.quantity}</td>
                      <td className="py-1.5 px-2 text-emerald-400 font-semibold">€{Number(t.totalPrice).toFixed(2)}</td>
                      <td className="py-1.5 px-2 text-slate-400 font-sans truncate max-w-[90px]">{t.traderName}</td>
                      <td className="py-1.5 px-2 text-right">
                        <span className="px-1.5 py-0.5 text-[9px] rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          {t.status || 'CONFIRMED'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
