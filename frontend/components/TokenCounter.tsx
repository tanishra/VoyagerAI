'use client';

import { Coins } from 'lucide-react';
import { clsx } from 'clsx';
import type { UsageEntry } from '@/lib/types';

interface TokenCounterProps {
  usage: UsageEntry[];
  totalInputTokens: number;
  totalOutputTokens: number;
  isStreaming?: boolean;
}

export default function TokenCounter({
  usage,
  totalInputTokens,
  totalOutputTokens,
  isStreaming,
}: TokenCounterProps) {
  const total = totalInputTokens + totalOutputTokens;
  if (total === 0 && !isStreaming) return null;

  return (
    <div
      className={clsx(
        'inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium',
        'bg-muted/40 text-muted-foreground/70 border border-border/30',
        isStreaming && 'animate-pulse',
      )}
    >
      <Coins className="h-3 w-3 shrink-0" />
      <span className="tabular-nums">
        {total.toLocaleString()} tokens
      </span>
      {total > 0 && (
        <>
          <span className="text-muted-foreground/30">·</span>
          <span className="tabular-nums text-muted-foreground/50">
            ↓{totalInputTokens.toLocaleString()} ↑{totalOutputTokens.toLocaleString()}
          </span>
        </>
      )}
    </div>
  );
}
