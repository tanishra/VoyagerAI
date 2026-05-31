'use client';

import { motion } from 'framer-motion';
import { ArrowLeft, Plane } from 'lucide-react';
import { Button } from '@/components/ui/button';
import BudgetSummary from '@/components/BudgetSummary';
import WarningsSection from '@/components/WarningsSection';
import DayCard from '@/components/DayCard';
import type { Itinerary } from '@/lib/types';

interface ItineraryViewProps {
  itinerary: Itinerary;
  onReplanDay: (dayNumber: number, reason: string) => void;
  replanLoading: boolean;
  onReset: () => void;
  budget?: number;
}

export default function ItineraryView({
  itinerary,
  onReplanDay,
  replanLoading,
  onReset,
  budget,
}: ItineraryViewProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="w-full max-w-4xl mx-auto space-y-6"
    >
      {/* Top bar */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex items-center justify-between"
      >
        <Button
          variant="ghost"
          id="plan-another-trip"
          onClick={onReset}
          className="text-sm text-muted-foreground hover:text-white transition-colors cursor-pointer"
          aria-label="Plan another trip"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Plan Another Trip
        </Button>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Plane className="w-4 h-4 text-purple-400" />
          <span>AI-Generated Itinerary</span>
        </div>
      </motion.div>

      {/* Budget Summary */}
      <BudgetSummary itinerary={itinerary} budget={budget} />

      {/* Warnings & Packing */}
      <WarningsSection
        warnings={itinerary.warnings}
        packingEssentials={itinerary.packing_essentials}
      />

      {/* Day Cards */}
      <div className="space-y-5">
        {itinerary.days.map((day, index) => (
          <DayCard
            key={day.day}
            day={day}
            index={index}
            onReplan={onReplanDay}
            replanLoading={replanLoading}
          />
        ))}
      </div>

      {/* Bottom reset */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="flex justify-center pt-4 pb-8"
      >
        <Button
          variant="outline"
          id="plan-another-trip-bottom"
          onClick={onReset}
          className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06] text-white/60 hover:text-white transition-all cursor-pointer"
        >
          <Plane className="w-4 h-4 mr-2" />
          Plan Another Trip
        </Button>
      </motion.div>
    </motion.div>
  );
}
