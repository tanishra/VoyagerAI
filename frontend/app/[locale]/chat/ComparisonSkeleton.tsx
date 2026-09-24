'use client';

import { motion } from 'framer-motion';

const TIER_DOTS = ['bg-chart-2/40', 'bg-primary/40', 'bg-accent-foreground/40'];

function Bar({ className }: { className: string }) {
  return <div className={`rounded bg-muted shimmer ${className}`} />;
}

function SkeletonCard({ index }: { index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.12, duration: 0.4, ease: 'easeOut' }}
      className="rounded-xl border border-border overflow-hidden flex flex-col bg-card"
    >
      <div className="px-4 pt-4 pb-3 border-b border-border/60">
        <div className="flex items-center gap-2 mb-2">
          <span className={`w-2.5 h-2.5 rounded-full ${TIER_DOTS[index] ?? 'bg-muted'}`} />
          <Bar className="h-3 w-16" />
        </div>
        <Bar className="h-8 w-2/3" />
      </div>
      <div className="px-4 py-2.5 border-b border-border/60 space-y-1.5">
        <Bar className="h-2.5 w-full" />
        <Bar className="h-2.5 w-5/6" />
        <Bar className="h-2.5 w-4/6" />
      </div>
      <div className="flex-1 px-4 py-2">
        <Bar className="h-2.5 w-1/2" />
      </div>
      <div className="p-3 border-t border-border/60">
        <Bar className="h-8 w-full" />
      </div>
    </motion.div>
  );
}

/**
 * Shimmer placeholder matching ComparisonView geometry — banner, matrix
 * strip, three tier cards — so the real card swaps in without reflow.
 */
export default function ComparisonSkeleton() {
  return (
    <div
      className="mt-3 rounded-xl border border-border bg-card overflow-hidden shadow-sm"
      aria-hidden="true"
      data-testid="comparison-skeleton"
    >
      <div className="w-full bg-muted shimmer" style={{ aspectRatio: '16 / 5' }} />
      <div className="px-4 py-3 border-b border-border space-y-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3">
            <Bar className="h-2.5 w-20" />
            <Bar className="h-2.5 w-16" />
            <Bar className="h-2.5 w-16" />
            <Bar className="h-2.5 w-16" />
          </div>
        ))}
      </div>
      <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4">
        {[0, 1, 2].map((i) => (
          <SkeletonCard key={i} index={i} />
        ))}
      </div>
    </div>
  );
}
