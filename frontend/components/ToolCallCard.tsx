'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Wrench, ChevronDown, Check, AlertCircle, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import type { ToolCallEntry } from '@/lib/types';

interface ToolCallCardProps {
  tool: ToolCallEntry;
}

export default function ToolCallCard({ tool }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = tool.status === 'running';
  const isError = tool.status === 'error';
  const isDone = tool.status === 'done';

  const durationMs =
    tool.started_at && tool.ended_at
      ? tool.ended_at - tool.started_at
      : null;

  return (
    <div
      className={clsx(
        'my-1.5 rounded-lg border overflow-hidden text-xs transition-colors',
        isError
          ? 'border-destructive/30 bg-destructive/5'
          : isRunning
            ? 'border-primary/30 bg-primary/5'
            : 'border-border/50 bg-muted/20',
      )}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-muted/40 transition-colors"
      >
        <span className="shrink-0">
          {isRunning ? (
            <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />
          ) : isError ? (
            <AlertCircle className="h-3.5 w-3.5 text-destructive" />
          ) : (
            <Check className="h-3.5 w-3.5 text-green-500" />
          )}
        </span>
        <Wrench className="h-3 w-3 text-muted-foreground shrink-0" />
        <span className="font-medium text-foreground">{tool.name}</span>
        {durationMs !== null && (
          <span className="text-muted-foreground/60 tabular-nums">
            {(durationMs / 1000).toFixed(1)}s
          </span>
        )}
        {isRunning && (
          <span className="text-primary/70 animate-pulse">running…</span>
        )}
        <ChevronDown
          className={clsx(
            'h-3.5 w-3.5 ml-auto text-muted-foreground transition-transform',
            expanded && 'rotate-180',
          )}
        />
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 pt-1 space-y-2">
              {tool.input && (
                <div>
                  <p className="text-muted-foreground/60 mb-0.5 font-medium">Input</p>
                  <pre className="text-xs text-muted-foreground/80 bg-muted/40 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap break-words">
                    {tool.input}
                  </pre>
                </div>
              )}
              {tool.output && (
                <div>
                  <p className="text-muted-foreground/60 mb-0.5 font-medium">Output</p>
                  <pre className="text-xs text-muted-foreground/80 bg-muted/40 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap break-words">
                    {tool.output}
                  </pre>
                </div>
              )}
              {tool.error && (
                <div>
                  <p className="text-destructive/70 mb-0.5 font-medium">Error</p>
                  <pre className="text-xs text-destructive/80 bg-destructive/5 rounded p-2 overflow-x-auto whitespace-pre-wrap break-words">
                    {tool.error}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
