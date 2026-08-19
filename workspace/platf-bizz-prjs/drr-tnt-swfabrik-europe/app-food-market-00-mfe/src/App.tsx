import React, { useState } from 'react';
import { Header } from './components/Header';
import { BackendCard } from './components/BackendCard';
import { BackendServiceConfig } from './types/market';
import { Layers, ShieldCheck, Cpu, Database, Network, GitBranch } from 'lucide-react';

const BACKEND_SERVICES: BackendServiceConfig[] = [
  // Column 1 (Services 01, 02, 03)
  {
    id: 'service-01',
    number: 1,
    name: 'Food Market 01 (Java / Spring)',
    tech: 'Java 25 • Spring Boot 3.4',
    techColor: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
    iconBg: 'bg-orange-600',
    marketId: 'MKT-EU-01-JAVA',
    schema: 'schm01',
    port: 8081,
    endpoint: 'http://localhost:8081/api/food-tradings',
    streamUrl: 'http://localhost:8081/api/food-tradings/stream',
    swaggerUrl: 'http://localhost:8081/swagger-ui.html',
    sampleItem: 'Spanish Extra Virgin Olive Oil 5L',
    samplePrice: 38.5,
    sampleTrader: 'Andalucia Cooperative SL',
  },
  {
    id: 'service-02',
    number: 2,
    name: 'Food Market 02 (Kotlin / Quarkus)',
    tech: 'Kotlin 2.1 • Quarkus 3.17',
    techColor: 'bg-violet-500/10 text-violet-400 border border-violet-500/20',
    iconBg: 'bg-violet-600',
    marketId: 'MKT-EU-02-QUARKUS',
    schema: 'schm02',
    port: 8082,
    endpoint: 'http://localhost:8082/api/food-tradings',
    streamUrl: 'http://localhost:8082/api/food-tradings/stream',
    swaggerUrl: 'http://localhost:8082/q/swagger-ui',
    sampleItem: 'Italian Parmigiano Reggiano DOP 24M',
    samplePrice: 65.0,
    sampleTrader: 'Emilia Foods Italia',
  },
  {
    id: 'service-03',
    number: 3,
    name: 'Food Market 03 (Go / Gin)',
    tech: 'Go 1.23 • Gin Web Framework',
    techColor: 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20',
    iconBg: 'bg-cyan-600',
    marketId: 'MKT-EU-03-GOLANG',
    schema: 'schm03',
    port: 8083,
    endpoint: 'http://localhost:8083/api/food-tradings',
    streamUrl: 'http://localhost:8083/api/food-tradings/stream',
    swaggerUrl: 'http://localhost:8083/swagger-ui',
    sampleItem: 'German Black Forest Ham 5kg',
    samplePrice: 48.0,
    sampleTrader: 'Bavaria Meats GmbH',
  },

  // Column 2 (Services 04, 05, 06)
  {
    id: 'service-04',
    number: 4,
    name: 'Food Market 04 (Python / FastAPI)',
    tech: 'Python 3.12 • FastAPI Async',
    techColor: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
    iconBg: 'bg-emerald-600',
    marketId: 'MKT-EU-04-PYTHON',
    schema: 'schm04',
    port: 8084,
    endpoint: 'http://localhost:8084/api/food-tradings',
    streamUrl: 'http://localhost:8084/api/food-tradings/stream',
    swaggerUrl: 'http://localhost:8084/docs',
    sampleItem: 'French Brie de Meaux AOP',
    samplePrice: 35.5,
    sampleTrader: 'Fromagerie de Paris',
  },
  {
    id: 'service-05',
    number: 5,
    name: 'Food Market 05 (TypeScript / NestJS)',
    tech: 'TypeScript 5.7 • NestJS 10',
    techColor: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
    iconBg: 'bg-rose-600',
    marketId: 'MKT-EU-05-NESTJS',
    schema: 'schm05',
    port: 8085,
    endpoint: 'http://localhost:8085/api/food-tradings',
    streamUrl: 'http://localhost:8085/api/food-tradings/stream',
    swaggerUrl: 'http://localhost:8085/swagger-ui',
    sampleItem: 'Belgian Chocolate Pralines Box 1kg',
    samplePrice: 22.5,
    sampleTrader: 'Brussels Master Chocolatiers',
  },
  {
    id: 'service-06',
    number: 6,
    name: 'Food Market 06 (.NET 8 / C#)',
    tech: '.NET 8 • C# Web API',
    techColor: 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20',
    iconBg: 'bg-indigo-600',
    marketId: 'MKT-EU-06-DOTNET',
    schema: 'schm06',
    port: 8086,
    endpoint: 'http://localhost:8086/api/food-tradings',
    streamUrl: 'http://localhost:8086/api/food-tradings/stream',
    swaggerUrl: 'http://localhost:8086/swagger-ui',
    sampleItem: 'Spanish Jamon Iberico de Bellota 7kg',
    samplePrice: 280.0,
    sampleTrader: 'Jabugo Dehesa Espana',
  },
];

export function App() {
  const [totalRefreshKey, setTotalRefreshKey] = useState<number>(0);
  const [activeStreamMap, setActiveStreamMap] = useState<Record<string, boolean>>({});

  const col1Services = BACKEND_SERVICES.slice(0, 3);
  const col2Services = BACKEND_SERVICES.slice(3, 6);

  const activeStreamCount = Object.values(activeStreamMap).filter(Boolean).length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Header
        totalTradings={6}
        activeStreams={activeStreamCount}
        totalMicroservices={BACKEND_SERVICES.length}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full space-y-6">
        {/* Architecture Overview Banner */}
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-indigo-600/20 border border-indigo-500/30 rounded-lg text-indigo-400">
              <Network className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">
                Multi-Tenant Polyglot Event-Driven Architecture (Hexagonal / Ports & Adapters)
              </h2>
              <p className="text-xs text-slate-400">
                Shared PostgreSQL Tenant DB (<code className="text-indigo-300">drr_tnt_bizapps_db</code>, schemas <code className="text-indigo-300">schm01..schm06</code>) & RabbitMQ Topic Exchange (<code className="text-indigo-300">marketplace.foodtrading.topic</code>)
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-xs text-slate-400">
            <span className="px-2.5 py-1 bg-slate-800/80 border border-slate-700 rounded-md">
              SOLID Principles
            </span>
            <span className="px-2.5 py-1 bg-slate-800/80 border border-slate-700 rounded-md">
              Zero-Trust PSS
            </span>
            <span className="px-2.5 py-1 bg-slate-800/80 border border-slate-700 rounded-md">
              SSE Broadcasting
            </span>
          </div>
        </div>

        {/* 2 Columns x 3 Sections Grid Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Column 1: Java (1), Kotlin (2), Go (3) */}
          <div className="space-y-6">
            <div className="flex items-center space-x-2 pb-1 border-b border-slate-800 text-xs font-bold text-slate-400 uppercase tracking-wider">
              <Layers className="w-3.5 h-3.5 text-blue-400" />
              <span>Column 1: JVM & Go Ecosystems</span>
            </div>

            {col1Services.map((svc) => (
              <BackendCard
                key={svc.id}
                config={svc}
                onTradingAdded={() => setTotalRefreshKey((k) => k + 1)}
                onStreamStateChange={(active) =>
                  setActiveStreamMap((prev) => ({ ...prev, [svc.id]: active }))
                }
              />
            ))}
          </div>

          {/* Column 2: Python (4), TypeScript (5), .NET (6) */}
          <div className="space-y-6">
            <div className="flex items-center space-x-2 pb-1 border-b border-slate-800 text-xs font-bold text-slate-400 uppercase tracking-wider">
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              <span>Column 2: Scripting, Node & CLR Ecosystems</span>
            </div>

            {col2Services.map((svc) => (
              <BackendCard
                key={svc.id}
                config={svc}
                onTradingAdded={() => setTotalRefreshKey((k) => k + 1)}
                onStreamStateChange={(active) =>
                  setActiveStreamMap((prev) => ({ ...prev, [svc.id]: active }))
                }
              />
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-4 text-center text-xs text-slate-500">
        Darueira Private Cloud Platform © 2026 • Tenant: swfabrik-europe • Project: marketplaces • Environment: dev
      </footer>
    </div>
  );
}

export default App;
