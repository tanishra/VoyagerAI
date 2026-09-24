'use client';

import { motion } from 'framer-motion';

function Bar({ className }: { className: string }) {
  return <div className={`rounded bg-muted shimmer ${className}`} />;
}

/**
 * Shimmer placeholder for the day-by-day itinerary while refine_itinerary
 * runs — destination header, meta chips, day rows.
 */
export default function ItinerarySkeleton({ days = 5 }: { days?: number }) {
  return (
    <div
      className="mt-3 rounded-xl border border-border bg-card overflow-hidden shadow-sm p-4"
      aria-hidden="true"
      data-testid="itinerary-skeleton"
    >
      <Bar className="h-7 w-1/2 mb-2" />
      <div className="flex gap-2 mb-4">
        <Bar className="h-5 w-20 rounded-full" />
        <Bar className="h-5 w-24 rounded-full" />
        <Bar className="h-5 w-16 rounded-full" />
      </div>
      <div className="space-y-2.5">
        {Array.from({ length: days }, (_, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, duration: 0.3, ease: 'easeOut' }}
            className="flex gap-3 p-2.5 rounded-lg bg-muted/50 border border-border/60"
          >
            <div className="w-6 h-6 shrink-0 rounded bg-muted shimmer" />
            <div className="flex-1 space-y-1.5">
              <Bar className="h-3 w-2/5" />
              <Bar className="h-2.5 w-full" />
              <Bar className="h-2.5 w-4/5" />
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
