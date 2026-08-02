'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, ChevronDown, ChevronUp, Wallet, Scale, Sparkles } from 'lucide-react';
import type { ComparisonData, PlanTier } from '@/lib/types';

const TIER_CONFIG: Record<string, { icon: typeof Wallet; label: string; color: string; border: string; bg: string }> = {
  budget: { icon: Wallet, label: 'Budget', color: 'text-emerald-400', border: 'border-emerald-500/20', bg: 'bg-emerald-500/5' },
  balanced: { icon: Scale, label: 'Balanced', color: 'text-sky-400', border: 'border-sky-500/30', bg: 'bg-sky-500/5' },
  premium: { icon: Sparkles, label: 'Premium', color: 'text-amber-400', border: 'border-amber-500/20', bg: 'bg-amber-500/5' },
};

function PlanCard({ plan, onSelect }: { plan: PlanTier; onSelect: (tier: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = TIER_CONFIG[plan.tier] ?? TIER_CONFIG.balanced;
  const Icon = cfg.icon;
  const itinerary = plan.itinerary;
  const days = itinerary.days ?? [];
  const breakdown = plan.cost_breakdown;

  return (
    <div className={`rounded-xl border ${cfg.border} ${cfg.bg} overflow-hidden flex flex-col`}>
      {/* Tier header */}
      <div className="px-4 py-3 border-b border-white/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`w-4 h-4 ${cfg.color}`} />
            <span className={`font-semibold text-sm capitalize ${cfg.color}`}>{cfg.label}</span>
          </div>
          <span className="text-lg font-bold text-white">
            ${itinerary.estimated_total_cost_usd ?? breakdown?.total ?? 'N/A'}
          </span>
        </div>
      </div>

      {/* Cost breakdown */}
      {breakdown && (
        <div className="px-4 py-2.5 border-b border-white/5">
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Stay</span>
              <span className="text-white/80">${breakdown.accommodation}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Food</span>
              <span className="text-white/80">${breakdown.food}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Activities</span>
              <span className="text-white/80">${breakdown.activities}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Transport</span>
              <span className="text-white/80">${breakdown.transport}</span>
            </div>
          </div>
        </div>
      )}

      {/* Tradeoffs */}
      {plan.tradeoffs && plan.tradeoffs.length > 0 && (
        <div className="px-4 py-2.5 border-b border-white/5">
          <ul className="space-y-1">
            {plan.tradeoffs.slice(0, 3).map((t, i) => (
              <li key={i} className="text-xs text-white/60 flex items-start gap-1.5">
                <span className="text-white/40 mt-0.5">•</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Day summary (expandable) */}
      <div className="flex-1">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full px-4 py-2 flex items-center justify-between text-xs text-muted-foreground hover:text-white/80 transition-colors cursor-pointer"
        >
          <span>{days.length} days · {itinerary.destination}</span>
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-3 space-y-1.5">
                {days.map((day) => (
                  <div key={day.day} className="p-2 rounded-lg bg-white/5">
                    <p className="font-medium text-white/90 text-xs">
                      Day {day.day} — {day.theme ?? 'Day ' + day.day}
                    </p>
                    <p className="text-muted-foreground text-[10px] mt-0.5">
                      {day.morning?.activity ?? '—'} → {day.afternoon?.activity ?? '—'} → {day.evening?.activity ?? '—'}
                    </p>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Select button */}
      <div className="p-3 border-t border-white/5">
        <button
          onClick={() => onSelect(plan.tier)}
          className="w-full py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-white/80 hover:text-white transition-all cursor-pointer"
        >
          Select {cfg.label}
        </button>
      </div>
    </div>
  );
}

export default function ComparisonView({
  data,
  onSelect,
}: {
  data: ComparisonData;
  onSelect: (tier: string) => void;
}) {
  const matrix = data.comparison_matrix;
  const tiers = ['budget', 'balanced', 'premium'] as const;

  return (
    <div className="mt-3 rounded-xl border border-white/10 bg-black/20 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5">
        <h3 className="font-semibold text-white flex items-center gap-2 text-sm">
          <Globe className="w-4 h-4 text-sky-400" />
          Compare Plans
        </h3>
      </div>

      {/* Comparison matrix strip */}
      {matrix && (
        <div className="px-4 py-3 border-b border-white/5 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground">
                <th className="text-left font-normal py-1 pr-3"></th>
                {tiers.map((t) => (
                  <th key={t} className="text-left font-normal py-1 px-2 capitalize">{t}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {([
                { label: 'Cost', key: 'total_cost' as const, prefix: '$' },
                { label: 'Stay', key: 'accommodation_type' as const },
                { label: 'Food', key: 'food_style' as const },
                { label: 'Transport', key: 'transport_mode' as const },
              ]).map((row) => (
                <tr key={row.key} className="border-t border-white/5">
                  <td className="py-1.5 pr-3 text-muted-foreground">{row.label}</td>
                  {tiers.map((t) => (
                    <td key={t} className="py-1.5 px-2 text-white/80">
                      {row.prefix}{matrix[row.key]?.[t] ?? '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Plan cards */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.plans.map((plan) => (
          <PlanCard key={plan.tier} plan={plan} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}
