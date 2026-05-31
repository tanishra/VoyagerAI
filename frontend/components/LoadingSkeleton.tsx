'use client';

import { motion } from 'framer-motion';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

export default function LoadingSkeleton() {
  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Budget summary skeleton */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="space-y-2">
                <Skeleton className="h-7 w-48 bg-white/[0.06]" />
                <Skeleton className="h-4 w-32 bg-white/[0.04]" />
              </div>
              <Skeleton className="h-10 w-28 rounded-full bg-white/[0.06]" />
            </div>
            <Skeleton className="h-3 w-full rounded-full bg-white/[0.04]" />
            <div className="mt-4 flex gap-6">
              <Skeleton className="h-4 w-40 bg-white/[0.04]" />
              <Skeleton className="h-4 w-40 bg-white/[0.04]" />
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Day card skeletons */}
      {[0, 1, 2, 3].map((i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 * (i + 1) }}
        >
          <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl overflow-hidden">
            {/* Top gradient bar */}
            <div className="h-1 bg-gradient-to-r from-white/[0.06] via-white/[0.1] to-white/[0.06]" />
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="space-y-2">
                  <Skeleton className="h-5 w-20 bg-white/[0.06]" />
                  <Skeleton className="h-6 w-44 bg-white/[0.06]" />
                </div>
                <Skeleton className="h-8 w-20 rounded-full bg-white/[0.06]" />
              </div>
            </CardHeader>
            <CardContent className="space-y-5 pb-6">
              {/* Three time slots */}
              {[0, 1, 2].map((j) => (
                <div key={j} className="space-y-2">
                  <Skeleton className="h-4 w-24 bg-white/[0.06]" />
                  <div className="ml-4 space-y-1.5">
                    <Skeleton className="h-5 w-3/4 bg-white/[0.04]" />
                    <div className="flex gap-4">
                      <Skeleton className="h-3 w-28 bg-white/[0.03]" />
                      <Skeleton className="h-3 w-16 bg-white/[0.03]" />
                      <Skeleton className="h-3 w-20 bg-white/[0.03]" />
                    </div>
                  </div>
                </div>
              ))}
              {/* Transport & accommodation */}
              <div className="flex gap-4 pt-2 border-t border-white/5">
                <Skeleton className="h-4 w-36 bg-white/[0.04]" />
                <Skeleton className="h-4 w-36 bg-white/[0.04]" />
              </div>
              {/* Tips */}
              <div className="space-y-1.5 pt-2">
                <Skeleton className="h-3 w-16 bg-white/[0.06]" />
                <Skeleton className="h-3 w-full bg-white/[0.03]" />
                <Skeleton className="h-3 w-4/5 bg-white/[0.03]" />
              </div>
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}
