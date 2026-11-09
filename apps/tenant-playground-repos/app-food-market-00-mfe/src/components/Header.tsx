import React from 'react';
import { ShieldCheck, Server, Database, Layers, Radio, Globe2 } from 'lucide-react';

interface HeaderProps {
  totalTradings: number;
  activeStreams: number;
  totalMicroservices: number;
}

export const Header: React.FC<HeaderProps> = ({ totalTradings, activeStreams, totalMicroservices }) => {
  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50 backdrop-blur-md bg-opacity-90">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-gradient-to-tr from-blue-600 to-indigo-500 rounded-xl shadow-lg shadow-blue-500/20 text-white">
              <Globe2 className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-bold tracking-tight text-white">
                  Darueira European Food Marketplaces
                </h1>
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Dev Cluster
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Polyglot Hexagonal Architecture Demo • Tenant: <span className="text-slate-200 font-medium">swfabrik-europe</span> • Project: <span className="text-slate-200 font-medium">marketplaces</span>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Zero Trust Badge */}
            <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/80 border border-slate-700 rounded-lg text-xs">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="text-slate-300">Zero Trust PSS</span>
              <span className="font-semibold text-emerald-400">Restricted</span>
            </div>

            {/* Microservices Count */}
            <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/80 border border-slate-700 rounded-lg text-xs">
              <Server className="w-4 h-4 text-blue-400" />
              <span className="text-slate-300">Backends:</span>
              <span className="font-bold text-white">{totalMicroservices} Polyglots</span>
            </div>

            {/* Total Tradings */}
            <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/80 border border-slate-700 rounded-lg text-xs">
              <Database className="w-4 h-4 text-purple-400" />
              <span className="text-slate-300">DB Records:</span>
              <span className="font-bold text-purple-300">{totalTradings}</span>
            </div>

            {/* Active SSE */}
            <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/80 border border-slate-700 rounded-lg text-xs">
              <Radio className="w-4 h-4 text-amber-400 animate-pulse" />
              <span className="text-slate-300">Live SSE:</span>
              <span className="font-bold text-amber-300">{activeStreams} / 6</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
