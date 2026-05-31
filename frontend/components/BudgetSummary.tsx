'use client';

import { useState, useEffect, memo } from 'react';
import { motion } from 'framer-motion';
import {
  DollarSign,
  Calendar,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Eye,
  Sun,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import BudgetGauge from '@/components/BudgetGauge';
import type { Itinerary } from '@/lib/types';

interface BudgetSummaryProps {
  itinerary: Itinerary;
  budget?: number;
}

const statusConfig = {
  within: { label: 'Within Budget', classes: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', icon: TrendingUp },
  over: { label: 'Over Budget', classes: 'bg-red-500/15 text-red-400 border-red-500/30', icon: AlertTriangle },
  under: { label: 'Under Budget', classes: 'bg-amber-500/15 text-amber-400 border-amber-500/30', icon: TrendingDown },
};

function AnimatedNumber({ value, prefix = '' }: { value: number; prefix?: string }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    let start = 0;
    const duration = 800;
    const step = Math.max(1, Math.floor(value / 30));
    const timer = setInterval(() => {
      start += step;
      if (start >= value) {
        setDisplay(value);
        clearInterval(timer);
      } else {
        setDisplay(start);
      }
    }, duration / (value / step));
    return () => clearInterval(timer);
    // Only animate on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <span>{prefix}{display.toLocaleString()}</span>;
}

const BudgetSummary = memo(function BudgetSummary({ itinerary, budget }: BudgetSummaryProps) {
  const config = statusConfig[itinerary.budget_status];
  const userBudget = budget ?? itinerary.estimated_total_cost_usd;
  const budgetPercent = Math.min(100, Math.round((itinerary.estimated_total_cost_usd / userBudget) * 100));

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card className="relative overflow-hidden border-white/10 bg-white/[0.03] backdrop-blur-2xl shadow-xl">
        <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-sky-500 via-blue-500 to-indigo-500" />

        <CardContent className="p-6 md:p-8">
          <div className="flex flex-col md:flex-row md:items-center gap-6">
            {/* Gauge */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 }}
              className="flex justify-center"
            >
              <BudgetGauge percent={budgetPercent} status={itinerary.budget_status} />
            </motion.div>

            {/* Details */}
            <div className="flex-1 space-y-4">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider">Estimated Total Cost</p>
                  <div className="flex items-baseline gap-1 mt-0.5">
                    <DollarSign className="w-5 h-5 text-emerald-400" />
                    <span className="text-3xl font-bold text-white tabular-nums">
                      <AnimatedNumber value={itinerary.estimated_total_cost_usd} />
                    </span>
                    <span className="text-sm text-muted-foreground ml-1">USD</span>
                  </div>
                </div>
                <Badge variant="outline" className={`${config.classes} px-4 py-1.5 text-sm font-medium`}>
                  <config.icon className="w-3.5 h-3.5 mr-1.5" />
                  {config.label}
                </Badge>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-3 gap-4">
                <motion.div whileHover={{ y: -2 }} className="p-3 rounded-lg bg-white/[0.03] border border-white/5 hover:border-white/20 transition-colors">
                  <p className="text-xs text-muted-foreground">Per Day Avg</p>
                  <p className="text-lg font-semibold text-white/80 tabular-nums">
                    ${Math.round(itinerary.estimated_total_cost_usd / itinerary.total_days).toLocaleString()}
                  </p>
                </motion.div>
                <motion.div whileHover={{ y: -2 }} className="p-3 rounded-lg bg-white/[0.03] border border-white/5 hover:border-white/20 transition-colors">
                  <p className="text-xs text-muted-foreground">Duration</p>
                  <p className="text-lg font-semibold text-white/80 flex items-center gap-1.5">
                    <Calendar className="w-4 h-4 text-sky-400" />
                    <AnimatedNumber value={itinerary.total_days} />
                    <span className="text-sm text-muted-foreground">days</span>
                  </p>
                </motion.div>
                <motion.div whileHover={{ y: -2 }} className="p-3 rounded-lg bg-white/[0.03] border border-white/5 hover:border-white/20 transition-colors">
                  <p className="text-xs text-muted-foreground">{budget ? 'Your Budget' : 'Total'}</p>
                  <p className="text-lg font-semibold text-white/80 tabular-nums flex items-center gap-1">
                    <DollarSign className="w-4 h-4 text-emerald-400" />
                    <AnimatedNumber value={userBudget} />
                  </p>
                </motion.div>
              </div>

              {/* Notes */}
              <div className="grid sm:grid-cols-2 gap-3">
                {itinerary.visa_note && (
                  <motion.div
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="flex items-start gap-2.5 p-3 rounded-lg bg-white/[0.03] border border-white/5"
                  >
                    <Eye className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-muted-foreground font-medium mb-0.5">Visa Note</p>
                      <p className="text-sm text-white/70">{itinerary.visa_note}</p>
                    </div>
                  </motion.div>
                )}
                {itinerary.best_season_note && (
                  <motion.div
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="flex items-start gap-2.5 p-3 rounded-lg bg-white/[0.03] border border-white/5"
                  >
                    <Sun className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-muted-foreground font-medium mb-0.5">Best Season</p>
                      <p className="text-sm text-white/70">{itinerary.best_season_note}</p>
                    </div>
                  </motion.div>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
});

export default BudgetSummary;
