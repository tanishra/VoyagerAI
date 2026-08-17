'use client';

import { motion } from 'framer-motion';
import { Check, AlertCircle, Loader2, Circle } from 'lucide-react';
import { clsx } from 'clsx';
import type { ToolCallEntry } from '@/lib/types';

interface SubagentTimelineProps {
  toolCalls: ToolCallEntry[];
}

export default function SubagentTimeline({ toolCalls }: SubagentTimelineProps) {
  if (toolCalls.length === 0) return null;

  return (
    <div className="my-2">
      <div className="relative pl-5">
        {/* Vertical line */}
        <div className="absolute left-[7px] top-1 bottom-1 w-px bg-border/60" />

        {toolCalls.map((tc, i) => (
          <motion.div
            key={`${tc.run_id}-${i}`}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: i * 0.05 }}
            className="relative mb-2 last:mb-0"
          >
            {/* Status dot */}
            <div
              className={clsx(
                'absolute -left-[18px] top-0.5 flex items-center justify-center rounded-full h-3.5 w-3.5 ring-2 ring-background',
                tc.status === 'running' && 'bg-primary/20',
                tc.status === 'done' && 'bg-green-500/20',
                tc.status === 'error' && 'bg-destructive/20',
              )}
            >
              {tc.status === 'running' ? (
                <Loader2 className="h-2.5 w-2.5 text-primary animate-spin" />
              ) : tc.status === 'done' ? (
                <Check className="h-2.5 w-2.5 text-green-500" />
              ) : tc.status === 'error' ? (
                <AlertCircle className="h-2.5 w-2.5 text-destructive" />
              ) : (
                <Circle className="h-2 w-2 text-muted-foreground" />
              )}
            </div>

            {/* Tool name + duration */}
            <div className="flex items-center gap-2 text-xs">
              <span className="font-medium text-foreground">{tc.name}</span>
              {tc.started_at && tc.ended_at && (
                <span className="text-muted-foreground/50 tabular-nums">
                  {((tc.ended_at - tc.started_at) / 1000).toFixed(1)}s
                </span>
              )}
              {tc.status === 'running' && (
                <span className="text-primary/60 animate-pulse">running…</span>
              )}
              {tc.status === 'error' && (
                <span className="text-destructive/60">failed</span>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
