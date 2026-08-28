'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ChevronDown, Loader2, Cpu } from 'lucide-react';
import { clsx } from 'clsx';
import { useTranslations } from 'next-intl';
import ThinkingBlock from '@/components/ThinkingBlock';
import SubagentTimeline from '@/components/SubagentTimeline';
import type { ActivityData } from '@/lib/types';

interface ActivityPanelProps {
  activity: ActivityData | null;
  activeWorkers: string[];
  isStreaming: boolean;
  hasText: boolean;
  progressMap?: Record<string, string>;
  workerIcons?: Record<string, React.ReactNode>;
  workerLabels?: Record<string, string>;
}

export default function ActivityPanel({
  activity,
  activeWorkers,
  isStreaming,
  hasText,
  progressMap,
  workerIcons,
  workerLabels,
}: ActivityPanelProps) {
  const t = useTranslations('chat');
  const [expanded, setExpanded] = useState(false);
  const [userOverride, setUserOverride] = useState(false);
  const prevHasText = useRef(false);

  const hasThinking = (activity?.thinking?.length ?? 0) > 0;
  const hasToolCalls = (activity?.tool_calls?.length ?? 0) > 0;
  const hasActivity = hasThinking || hasToolCalls;
  const runningCount = activeWorkers.length;
  const completedCount = useMemo(
    () => (activity?.tool_calls ?? []).filter((tc) => tc.status === 'done').length,
    [activity?.tool_calls],
  );
  const totalTokens = (activity?.total_input_tokens ?? 0) + (activity?.total_output_tokens ?? 0);

  // Auto-expand when streaming starts and no text yet
  // Auto-collapse when text starts streaming
  useEffect(() => {
    if (userOverride) return;
    if (isStreaming && !hasText && hasActivity) {
      setExpanded(true);
    } else if (isStreaming && hasText && !prevHasText.current) {
      setExpanded(false);
    }
    prevHasText.current = hasText;
  }, [isStreaming, hasText, hasActivity, userOverride]);

  // Reset user override when streaming ends
  useEffect(() => {
    if (!isStreaming) {
      setUserOverride(false);
    }
  }, [isStreaming]);

  const handleToggle = () => {
    setUserOverride(true);
    setExpanded((v) => !v);
  };

  if (!hasActivity && !isStreaming) return null;

  // Build collapsed summary
  const summaryParts: string[] = [];
  if (runningCount > 0) {
    summaryParts.push(t('activityRunning', { count: runningCount }));
  }
  if (completedCount > 0 && runningCount === 0) {
    summaryParts.push(t('activityCompleted', { count: completedCount }));
  }
  if (totalTokens > 0) {
    const k = totalTokens >= 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : String(totalTokens);
    summaryParts.push(`${k} tokens`);
  }
  const summary = summaryParts.join(' · ') || t('activityPanel');

  return (
    <div className="my-2 rounded-lg border border-border/50 bg-muted/20 overflow-hidden">
      {/* Collapsed header / summary line */}
      <button
        onClick={handleToggle}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs text-muted-foreground hover:bg-muted/40 transition-colors"
      >
        <Activity className="h-3.5 w-3.5 shrink-0" />
        {isStreaming && runningCount > 0 ? (
          <Loader2 className="h-3 w-3 animate-spin text-primary shrink-0" />
        ) : (
          <Cpu className="h-3 w-3 shrink-0" />
        )}
        <span className="font-medium truncate flex-1 text-left">{summary}</span>
        {isStreaming && runningCount > 0 && (
          <span className="flex gap-0.5 ml-1 shrink-0">
            <span className="h-1 w-1 rounded-full bg-current animate-pulse" />
            <span className="h-1 w-1 rounded-full bg-current animate-pulse [animation-delay:200ms]" />
            <span className="h-1 w-1 rounded-full bg-current animate-pulse [animation-delay:400ms]" />
          </span>
        )}
        <ChevronDown
          className={clsx(
            'h-3.5 w-3.5 ml-auto shrink-0 transition-transform',
            expanded && 'rotate-180',
          )}
        />
      </button>

      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 pt-1 max-h-[400px] overflow-y-auto space-y-2">
              {hasThinking && activity?.thinking && (
                <ThinkingBlock blocks={activity.thinking} isStreaming={isStreaming && !hasText} />
              )}
              {hasToolCalls && activity?.tool_calls && (
                <SubagentTimeline
                  toolCalls={activity.tool_calls}
                  progressMap={progressMap}
                  isStreaming={isStreaming}
                />
              )}
              {runningCount > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {activeWorkers.map((tool) => (
                    <span
                      key={tool}
                      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-primary/10 border border-primary/20 text-[10px] font-medium text-primary"
                    >
                      <Loader2 className="w-3 h-3 animate-spin" />
                      {workerIcons?.[tool]}
                      {workerLabels?.[tool] ?? tool}
                    </span>
                  ))}
                </div>
              )}
              {totalTokens > 0 && (
                <div className="text-[10px] text-muted-foreground/60 pt-1 border-t border-border/30">
                  {t('tokensUsed', {
                    input: activity?.total_input_tokens ?? 0,
                    output: activity?.total_output_tokens ?? 0,
                  })}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
