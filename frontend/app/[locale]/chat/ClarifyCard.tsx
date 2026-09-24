'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Check, Send, ChevronLeft, ChevronRight } from 'lucide-react';
import { useMessages, useTranslations } from 'next-intl';
import type { ClarifyData, ClarifyQuestion } from '@/lib/types';

function optionKey(label: string, value?: string): string {
  return (value ?? label).toLowerCase().replace(/\s+/g, '_');
}

export default function ClarifyCard({
  data,
  onSend,
  disabled,
}: {
  data: ClarifyData;
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const t = useTranslations();
  const messages = useMessages() as Record<string, unknown> | undefined;
  const questions = data.questions ?? [];
  // selections[i] = set of chosen option labels for question i, or Other text
  const [selections, setSelections] = useState<Record<number, Set<string>>>({});
  const [others, setOthers] = useState<Record<number, string>>({});
  const [otherOpen, setOtherOpen] = useState<Record<number, boolean>>({});
  const [active, setActive] = useState(0);

  const localized = (q: ClarifyQuestion, label: string, value?: string): string => {
    // Read the messages tree directly — t() logs MISSING_MESSAGE errors for
    // option keys that intentionally don't exist (free-text/dynamic values).
    const opts = (messages?.clarifyOptions as Record<string, Record<string, unknown>> | undefined)?.[q.field];
    const hit = opts?.[optionKey(label, value)];
    return typeof hit === 'string' ? hit : label;
  };

  const answerFor = (qi: number, q: ClarifyQuestion): string[] => {
    const picked = [...(selections[qi] ?? [])].map((l) => {
      const opt = q.options.find((o) => o.label === l);
      return localized(q, l, opt?.value);
    });
    const other = others[qi]?.trim();
    if (other) picked.push(other);
    return picked;
  };

  const answered = (qi: number) => answerFor(qi, questions[qi]).length > 0;

  const nextUnanswered = (from: number): number => {
    for (let i = 1; i < questions.length; i++) {
      const idx = (from + i) % questions.length;
      if (!answered(idx)) return idx;
    }
    return from;
  };

  const toggle = (qi: number, label: string, multi: boolean) => {
    setSelections((prev) => {
      const next = { ...prev };
      const set = new Set(next[qi] ?? []);
      if (set.has(label)) {
        set.delete(label);
      } else {
        if (!multi) set.clear();
        set.add(label);
      }
      next[qi] = set;
      return next;
    });
    // single-select: jump to next unanswered tab (Claude-style flow)
    if (!multi && !(selections[qi]?.has(label))) {
      const nxt = nextUnanswered(qi);
      if (nxt !== qi) setActive(nxt);
    }
  };

  const allAnswered =
    questions.length > 0 && questions.every((q, i) => answerFor(i, q).length > 0);

  const handleSend = () => {
    if (!allAnswered) return;
    const text = questions
      .map((q, i) => `${q.header}: ${answerFor(i, q).join(', ')}`)
      .join('; ');
    onSend(text);
  };

  const q = questions[active];
  if (!q) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="mt-3 rounded-xl border border-border bg-card overflow-hidden shadow-sm"
    >
      {/* tab strip — one chip per question, switch freely */}
      {questions.length > 1 && (
        <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-border px-3 pt-3 pb-0">
          {questions.map((qq, i) => (
            <button
              key={qq.field || i}
              type="button"
              role="tab"
              aria-selected={i === active}
              onClick={() => setActive(i)}
              className={`inline-flex shrink-0 items-center gap-1 rounded-t-lg border-b-2 px-2.5 py-1.5 text-[11px] font-medium transition-colors cursor-pointer ${
                i === active
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {answered(i) && <Check className="w-3 h-3 text-primary" />}
              {qq.header}
            </button>
          ))}
        </div>
      )}

      <div className="p-4">
        <div className="flex items-center gap-2 mb-1.5">
          {questions.length <= 1 && (
            <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {q.header}
            </span>
          )}
          <span className="text-[10px] text-muted-foreground/60">
            {q.multi_select ? t('clarify.pickMany') : t('clarify.pickOne')}
          </span>
        </div>
        <p className="text-sm text-foreground mb-3">{q.question}</p>

        {/* option rows */}
        <div className="flex flex-col gap-1.5">
          {q.options.map((opt) => {
            const selected = selections[active]?.has(opt.label) ?? false;
            return (
              <button
                key={opt.label}
                type="button"
                disabled={disabled}
                aria-pressed={selected}
                onClick={() => toggle(active, opt.label, q.multi_select)}
                className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 text-left text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-60 ${
                  selected
                    ? 'border-primary/50 bg-primary/10 text-foreground'
                    : 'border-border bg-transparent text-foreground/70 hover:border-primary/40 hover:text-foreground'
                }`}
              >
                <span
                  className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border ${
                    selected ? 'border-primary bg-primary' : 'border-muted-foreground/40'
                  }`}
                >
                  {selected && <Check className="w-2 h-2 text-primary-foreground" />}
                </span>
                <span className="flex-1">{localized(q, opt.label, opt.value)}</span>
                {opt.description && (
                  <span className="text-[10px] text-muted-foreground/70">{opt.description}</span>
                )}
              </button>
            );
          })}
          <button
            type="button"
            disabled={disabled}
            aria-pressed={otherOpen[active] ?? false}
            onClick={() => setOtherOpen((p) => ({ ...p, [active]: !p[active] }))}
            className={`flex items-center gap-2.5 rounded-lg border border-dashed px-3 py-2 text-left text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-60 ${
              otherOpen[active]
                ? 'border-primary/50 bg-primary/10 text-foreground'
                : 'border-border text-muted-foreground hover:border-primary/40 hover:text-foreground'
            }`}
          >
            <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border border-dashed border-muted-foreground/40" />
            {t('clarify.other')}
          </button>
        </div>
        {otherOpen[active] && (
          <input
            type="text"
            value={others[active] ?? ''}
            disabled={disabled}
            onChange={(e) => setOthers((p) => ({ ...p, [active]: e.target.value }))}
            placeholder={t('clarify.otherPlaceholder')}
            className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/50"
          />
        )}
      </div>

      <div className="flex items-center gap-2 px-4 pb-4">
        {questions.length > 1 && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label={t('clarify.prev')}
              disabled={disabled || active === 0}
              onClick={() => setActive((a) => Math.max(0, a - 1))}
              className="rounded-md border border-border p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40 cursor-pointer disabled:cursor-default"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="px-1 text-[10px] text-muted-foreground/70 tabular-nums">
              {active + 1}/{questions.length}
            </span>
            <button
              type="button"
              aria-label={t('clarify.next')}
              disabled={disabled || active === questions.length - 1}
              onClick={() => setActive((a) => Math.min(questions.length - 1, a + 1))}
              className="rounded-md border border-border p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40 cursor-pointer disabled:cursor-default"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !allAnswered}
          className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-default cursor-pointer"
        >
          <Send className="w-3 h-3" />
          {t('clarify.send')}
        </button>
      </div>
    </motion.div>
  );
}
