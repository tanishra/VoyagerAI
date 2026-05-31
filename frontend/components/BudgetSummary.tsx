'use client';

import { motion } from 'framer-motion';
import {
  DollarSign,
  MapPin,
  Calendar,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Eye,
  Sun,
} from 'lucide-react';
import { memo } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import type { Itinerary } from '@/lib/types';

interface BudgetSummaryProps {
  itinerary: Itinerary;
  budget?: number;
}

const statusConfig = {
  within: {
    label: 'Within Budget',
    classes: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    progressColor: 'bg-emerald-500',
    icon: TrendingUp,
  },
  over: {
    label: 'Over Budget',
    classes: 'bg-red-500/15 text-red-400 border-red-500/30',
    progressColor: 'bg-red-500',
    icon: AlertTriangle,
  },
  under: {
    label: 'Under Budget',
    classes: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    progressColor: 'bg-amber-500',
    icon: TrendingDown,
  },
};

const BudgetSummary = memo(function BudgetSummary({ itinerary, budget }: BudgetSummaryProps) {
  const config = statusConfig[itinerary.budget_status];
  const userBudget = budget ?? itinerary.estimated_total_cost_usd;
  const budgetPercent = Math.min(
    100,
    Math.round((itinerary.estimated_total_cost_usd / userBudget) * 100)
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card className="relative overflow-hidden border-white/10 bg-white/[0.03] backdrop-blur-2xl shadow-xl">
        {/* Top gradient */}
        <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-purple-500 via-blue-500 to-cyan-500" />

        <CardContent className="p-6 md:p-8">
          {/* Header row */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-purple-500/20">
                <MapPin className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">{itinerary.destination}</h2>
                <div className="flex items-center gap-3 text-sm text-muted-foreground mt-0.5">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    {itinerary.total_days} days
                  </span>
                </div>
              </div>
            </div>
            <Badge
              variant="outline"
              className={`${config.classes} px-4 py-1.5 text-sm font-medium border`}
            >
              <config.icon className="w-3.5 h-3.5 mr-1.5" />
              {config.label}
            </Badge>
          </div>

          {/* Cost section */}
          <div className="space-y-3 mb-6">
            <div className="flex items-end justify-between">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Estimated Total Cost</p>
                <div className="flex items-baseline gap-1">
                  <DollarSign className="w-5 h-5 text-emerald-400 mb-0.5" />
                  <span className="text-3xl font-bold text-white tabular-nums">
                    {itinerary.estimated_total_cost_usd.toLocaleString()}
                  </span>
                  <span className="text-sm text-muted-foreground ml-1">USD</span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">Per Day Avg</p>
                <p className="text-lg font-semibold text-white/80 tabular-nums">
                  ${Math.round(itinerary.estimated_total_cost_usd / itinerary.total_days).toLocaleString()}
                </p>
                {budget && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Budget: <span className="text-white/70">${budget.toLocaleString()} USD</span>
                  </p>
                )}
              </div>
            </div>
            <Progress
              value={budgetPercent}
              className="h-2 bg-white/[0.06]"
              aria-label="Budget utilization"
            />
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
        </CardContent>
      </Card>
    </motion.div>
  );
});

export default BudgetSummary;
