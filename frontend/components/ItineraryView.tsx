'use client';

import { motion } from 'framer-motion';
import { ArrowLeft, Plane } from 'lucide-react';
import { Button } from '@/components/ui/button';
import DestinationHero from '@/components/DestinationHero';
import BudgetSummary from '@/components/BudgetSummary';
import WarningsSection from '@/components/WarningsSection';
import TimelineDay from '@/components/TimelineDay';
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
          onClick={onReset}
          className="text-sm text-muted-foreground hover:text-white transition-colors cursor-pointer"
          aria-label="Plan another trip"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          New Trip
        </Button>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Plane className="w-4 h-4 text-sky-400" />
          <span>AI-Generated Itinerary</span>
        </div>
      </motion.div>

      {/* Destination Hero */}
      <DestinationHero destination={itinerary.destination} totalDays={itinerary.total_days} />

      {/* Budget Summary */}
      <BudgetSummary itinerary={itinerary} budget={budget} />

      {/* Warnings & Packing */}
      <WarningsSection
        warnings={itinerary.warnings}
        packingEssentials={itinerary.packing_essentials}
      />

      {/* Timeline Day Cards */}
      <div className="pl-1">
        {itinerary.days.map((day, index) => (
          <TimelineDay
            key={day.day}
            day={day}
            index={index}
            onReplan={onReplanDay}
            replanLoading={replanLoading}
            isLast={index === itinerary.days.length - 1}
          />
        ))}
      </div>

      {/* Bottom reset */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="flex justify-center pt-2 pb-8"
      >
        <Button
          variant="outline"
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
