'use client';

import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

function ShimmerBlock({ className }: { className?: string }) {
  return <div className={`shimmer rounded-lg ${className || ''}`} />;
}

export default function LoadingSkeleton() {
  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Hero skeleton */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>
        <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <ShimmerBlock className="w-12 h-12 rounded-2xl" />
              <div className="space-y-2 flex-1">
                <ShimmerBlock className="h-7 w-48" />
                <ShimmerBlock className="h-4 w-36" />
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Budget summary skeleton */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
      >
        <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl">
          <CardContent className="p-6">
            <div className="flex items-center gap-6">
              <ShimmerBlock className="w-[120px] h-[120px] rounded-full shrink-0" />
              <div className="flex-1 space-y-4">
                <ShimmerBlock className="h-6 w-40" />
                <ShimmerBlock className="h-10 w-56" />
                <div className="grid grid-cols-3 gap-3">
                  <ShimmerBlock className="h-16 rounded-lg" />
                  <ShimmerBlock className="h-16 rounded-lg" />
                  <ShimmerBlock className="h-16 rounded-lg" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Timeline day skeletons */}
      {[0, 1, 2, 3].map(i => (
        <div key={i} className="flex gap-4">
          <ShimmerBlock className="w-10 h-10 rounded-full shrink-0" />
          {i < 3 && <div className="w-px bg-white/[0.03]" />}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 * (i + 1) }}
            className="flex-1"
          >
            <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl overflow-hidden">
              <div className="h-0.5 shimmer" />
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShimmerBlock className="h-4 w-10" />
                    <ShimmerBlock className="h-5 w-32" />
                  </div>
                  <ShimmerBlock className="h-7 w-16 rounded-full" />
                </div>
              </CardHeader>
              <CardContent className="space-y-4 pb-5">
                <div className="grid grid-cols-3 gap-2">
                  {[0, 1, 2].map(j => (
                    <div key={j} className="space-y-2 p-3 rounded-xl shimmer">
                      <ShimmerBlock className="h-3 w-16" />
                      <ShimmerBlock className="h-4 w-full" />
                      <ShimmerBlock className="h-3 w-20" />
                    </div>
                  ))}
                </div>
                <div className="flex gap-4 pt-2">
                  <ShimmerBlock className="h-4 w-36" />
                  <ShimmerBlock className="h-4 w-36" />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      ))}
    </div>
  );
}
