'use client';

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, AlertCircle, Loader2, Circle, ChevronDown, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';
import type { ToolCallEntry } from '@/lib/types';
import ToolCallCard from '@/components/ToolCallCard';

interface SubagentTimelineProps {
  toolCalls: ToolCallEntry[];
  progressMap?: Record<string, string>;
  isStreaming?: boolean;
}

const SUBAGENT_NAMES = new Set([
  'researcher',
  'risk_detector',
  'constraint_analyzer',
  'validator',
  'enricher',
  'cost_optimizer',
  'multi_plan_generator',
  'quality_scorer',
]);

export default function SubagentTimeline({ toolCalls, progressMap, isStreaming }: SubagentTimelineProps) {
  if (toolCalls.length === 0) return null;

  const { topLevel, nestedByParent } = useMemo(() => {
    const topLevel: ToolCallEntry[] = [];
    const nestedByParent: Map<string, ToolCallEntry[]> = new Map();
    for (const tc of toolCalls) {
      if (tc.parent_run_id) {
        const arr = nestedByParent.get(tc.parent_run_id) ?? [];
        arr.push(tc);
        nestedByParent.set(tc.parent_run_id, arr);
      } else {
        topLevel.push(tc);
      }
    }
    return { topLevel, nestedByParent };
  }, [toolCalls]);

  return (
    <div className="my-2">
      <div className="relative pl-5">
        {/* Vertical line */}
        <div className="absolute left-[7px] top-1 bottom-1 w-px bg-border/60" />

        {topLevel.map((tc, i) => {
          const isSubagent = SUBAGENT_NAMES.has(tc.name);
          const nested = isSubagent ? (nestedByParent.get(tc.run_id) ?? []) : [];
          const hasNested = nested.length > 0;

          return (
            <SubagentEntry
              key={`${tc.run_id}-${i}`}
              tc={tc}
              hasNested={hasNested}
              nested={nested}
              progressMap={progressMap}
              isStreaming={isStreaming}
              index={i}
            />
          );
        })}
      </div>
    </div>
  );
}

function SubagentEntry({
  tc,
  hasNested,
  nested,
  progressMap,
  isStreaming,
  index,
}: {
  tc: ToolCallEntry;
  hasNested: boolean;
  nested: ToolCallEntry[];
  progressMap?: Record<string, string>;
  isStreaming?: boolean;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const progressDesc = progressMap?.[tc.run_id];
  const isRunning = tc.status === 'running';

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
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

      {/* Tool name + expand toggle for subagents */}
      <div className="flex items-center gap-2 text-xs">
        {hasNested && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="p-0.5 rounded hover:bg-muted transition-colors cursor-pointer"
            aria-label={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted-foreground" />
            )}
          </button>
        )}
        <span className="font-medium text-foreground">{tc.name}</span>
        {tc.started_at && tc.ended_at && (
          <span className="text-muted-foreground/50 tabular-nums">
            {((tc.ended_at - tc.started_at) / 1000).toFixed(1)}s
          </span>
        )}
        {isRunning && !hasNested && (
          <span className="text-primary/60 animate-pulse">running…</span>
        )}
        {tc.status === 'error' && (
          <span className="text-destructive/60">failed</span>
        )}
      </div>

      {/* Progress description */}
      {progressDesc && (
        <AnimatePresence mode="wait">
          <motion.p
            key={progressDesc}
            initial={{ opacity: 0, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 2 }}
            transition={{ duration: 0.15 }}
            className={clsx(
              'text-[11px] text-muted-foreground/70 mt-0.5 ml-1',
              isRunning && 'text-primary/60',
            )}
            title={progressDesc.length > 80 ? progressDesc : undefined}
          >
            {progressDesc.length > 80
              ? `${progressDesc.slice(0, 77)}...`
              : progressDesc}
          </motion.p>
        </AnimatePresence>
      )}

      {/* Nested tool calls */}
      <AnimatePresence>
        {expanded && hasNested && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden mt-1 ml-3 space-y-0"
          >
            {nested.map((ntc, j) => (
              <ToolCallCard key={`${ntc.run_id}-${j}`} tool={ntc} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
