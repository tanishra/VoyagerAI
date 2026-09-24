'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';

interface GenerationStatusProps {
  label: string;
  detail?: string | null;
}

/**
 * Always-visible status line under the streaming bubble while a pipeline
 * stage runs — stage label (localized) + rotating backend progress detail.
 */
export default function GenerationStatus({ label, detail }: GenerationStatusProps) {
  return (
    <div className="flex items-center gap-2 mt-2 mb-1" role="status" aria-live="polite">
      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
      <span className="text-xs font-medium text-foreground/80">{label}</span>
      <AnimatePresence mode="wait">
        {detail && (
          <motion.span
            key={detail}
            initial={{ opacity: 0, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 2 }}
            transition={{ duration: 0.15 }}
            className="text-[11px] text-muted-foreground/70 font-mono truncate max-w-[60%]"
            title={detail}
          >
            {detail}
          </motion.span>
        )}
      </AnimatePresence>
      <span className="flex gap-0.5 ml-auto shrink-0">
        <span className="h-1 w-1 rounded-full bg-primary/60 animate-pulse" />
        <span className="h-1 w-1 rounded-full bg-primary/60 animate-pulse [animation-delay:200ms]" />
        <span className="h-1 w-1 rounded-full bg-primary/60 animate-pulse [animation-delay:400ms]" />
      </span>
    </div>
  );
}
