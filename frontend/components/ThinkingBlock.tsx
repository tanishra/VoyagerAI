'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, ChevronDown } from 'lucide-react';
import { clsx } from 'clsx';
import type { ThinkingBlock as ThinkingBlockType } from '@/lib/types';

interface ThinkingBlockProps {
  blocks: ThinkingBlockType[];
  isStreaming?: boolean;
}

export default function ThinkingBlock({ blocks, isStreaming }: ThinkingBlockProps) {
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const text = blocks.map((b) => b.text).join('');
  const hasContent = text.length > 0;

  useEffect(() => {
    if (expanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [text, expanded]);

  if (!hasContent && !isStreaming) return null;

  return (
    <div className="my-2 rounded-lg border border-border/50 bg-muted/30 overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs text-muted-foreground hover:bg-muted/50 transition-colors"
      >
        <Brain className="h-3.5 w-3.5 shrink-0" />
        <span className="font-medium">
          {isStreaming && !hasContent ? 'Thinking…' : `Thinking${blocks.length > 1 ? ` (${blocks.length})` : ''}`}
        </span>
        {isStreaming && (
          <span className="flex gap-0.5 ml-1">
            <span className="h-1 w-1 rounded-full bg-current animate-pulse" />
            <span className="h-1 w-1 rounded-full bg-current animate-pulse [animation-delay:200ms]" />
            <span className="h-1 w-1 rounded-full bg-current animate-pulse [animation-delay:400ms]" />
          </span>
        )}
        <ChevronDown
          className={clsx(
            'h-3.5 w-3.5 ml-auto transition-transform',
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
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div
              ref={scrollRef}
              className="px-3 pb-3 pt-1 max-h-48 overflow-y-auto"
            >
              <p className="text-xs text-muted-foreground/80 whitespace-pre-wrap break-words font-mono leading-relaxed">
                {text}
                {isStreaming && (
                  <span className="inline-block w-1.5 h-3 ml-0.5 bg-current animate-pulse align-text-bottom" />
                )}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
