'use client';

import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Check, Send } from 'lucide-react';
import { useMessages, useTranslations } from 'next-intl';
import type { ClarifyData, ClarifyQuestion } from '@/lib/types';

function optionKey(label: string, value?: string): string {
  return (value ?? label).toLowerCase().replace(/\s+/g, '_');
}

// Only the most recently mounted/interacted card answers keyboard input —
// history can contain several clarify cards, and typing in the chat box or
// Other input must never trigger them.
let _activeClarify: symbol | null = null;

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
  // focused = index into options + trailing "Other" row of the active question
  const [focused, setFocused] = useState(0);
  const idRef = useRef(Symbol('clarify'));
  const keyHandlerRef = useRef<(e: KeyboardEvent) => void>(() => {});
  const otherInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const id = idRef.current;
    _activeClarify = id;
    return () => {
      if (_activeClarify === id) _activeClarify = null;
    };
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (_activeClarify !== idRef.current) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) return;
      keyHandlerRef.current(e);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    if (otherOpen[active]) otherInputRef.current?.focus();
  }, [otherOpen, active]);

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

  const switchTo = (idx: number) => {
    setActive(idx);
    setFocused(0);
  };

  const openOther = (qi: number) => {
    setOtherOpen((p) => ({ ...p, [qi]: true }));
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
      if (nxt !== qi) switchTo(nxt);
    }
  };

  const allAnswered =
    questions.length > 0 && questions.every((q, i) => answerFor(i, q).length > 0);

  const handleSend = () => {
    if (!allAnswered) return;
    const text = questions
      .map((q, i) => `${q.header}: ${answerFor(i, q).join(', ')}`)
      .join('; ');
    // Machine-readable record so the backend/model knows exactly which
    // fields are already answered — headers localize, fields don't.
    const fields: Record<string, string | string[]> = {};
    questions.forEach((q, i) => {
      const vals = [...(selections[i] ?? [])].map(
        (l) => q.options.find((o) => o.label === l)?.value ?? l,
      );
      const other = others[i]?.trim();
      if (other) vals.push(other);
      fields[q.field] = vals.length === 1 ? vals[0] : vals;
    });
    onSend(`${text}\n<clarify_answers>${JSON.stringify(fields)}</clarify_answers>`);
  };

  const q = questions[active];
  // focused index counts options + the trailing "Other" row
  const otherIndex = q?.options.length ?? 0;

  const onKeyDown = (e: KeyboardEvent) => {
    if (disabled || !q) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocused((f) => Math.min(otherIndex, f + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocused((f) => Math.max(0, f - 1));
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      switchTo(Math.max(0, active - 1));
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      switchTo(Math.min(questions.length - 1, active + 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (allAnswered) {
        handleSend();
      } else if (focused === otherIndex) {
        openOther(active);
      } else {
        const opt = q.options[focused];
        if (opt) toggle(active, opt.label, q.multi_select);
      }
    } else if (/^[1-9]$/.test(e.key)) {
      const i = Number(e.key) - 1;
      if (i < q.options.length) {
        setFocused(i);
        toggle(active, q.options[i].label, q.multi_select);
      } else if (i === otherIndex) {
        setFocused(otherIndex);
        openOther(active);
      }
    } else if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
      // Printable char while a row is focused → drop into "Other" (Claude-style)
      openOther(active);
      setOthers((p) => ({ ...p, [active]: (p[active] ?? '') + e.key }));
      setFocused(otherIndex);
    }
  };

  useEffect(() => {
    keyHandlerRef.current = onKeyDown;
  });

  if (!q) return null;

  const rowMarker = (i: number) => (
    <span className="w-3 shrink-0 text-center text-[10px] text-primary" aria-hidden>
      {focused === i ? '❯' : ''}
    </span>
  );

  const boxMarker = (selected: boolean, multi: boolean) => (
    <span
      className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center border ${
        multi ? 'rounded-[3px]' : 'rounded-full'
      } ${selected ? 'border-primary bg-primary' : 'border-muted-foreground/40'}`}
    >
      {selected && <Check className="w-2 h-2 text-primary-foreground" />}
    </span>
  );

  return (
    <motion.div
      onMouseDown={() => { _activeClarify = idRef.current; }}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="mt-3 rounded-xl border border-border bg-card overflow-hidden shadow-sm outline-none"
    >
      {/* tab strip — numbered, one per question, switch freely */}
      {questions.length > 1 && (
        <div role="tablist" className="flex gap-0.5 overflow-x-auto border-b border-border px-2 pt-2 pb-0">
          {questions.map((qq, i) => (
            <button
              key={qq.field || i}
              type="button"
              role="tab"
              aria-selected={i === active}
              onClick={() => switchTo(i)}
              className={`inline-flex shrink-0 items-center gap-1 rounded-t-md border-b-2 px-2 py-1 text-[11px] font-medium transition-colors cursor-pointer ${
                i === active
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {answered(i) ? (
                <Check className="w-3 h-3 text-primary" />
              ) : (
                <span aria-hidden className="text-muted-foreground/60 tabular-nums">{i + 1}</span>
              )}
              {qq.header}
            </button>
          ))}
        </div>
      )}

      <div className="px-3 pt-2.5 pb-1.5">
        <div className="flex items-center gap-2 mb-1">
          {questions.length <= 1 && (
            <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {q.header}
            </span>
          )}
          <span className="text-[10px] text-muted-foreground/60">
            {q.multi_select ? t('clarify.pickMany') : t('clarify.pickOne')}
          </span>
        </div>
        <p className="text-sm text-foreground mb-2">{q.question}</p>

        {/* compact option rows — flat, no bordered buttons */}
        <div className="flex flex-col">
          {q.options.map((opt, i) => {
            const selected = selections[active]?.has(opt.label) ?? false;
            return (
              <button
                key={opt.label}
                type="button"
                disabled={disabled}
                aria-pressed={selected}
                onMouseEnter={() => setFocused(i)}
                onClick={() => toggle(active, opt.label, q.multi_select)}
                className={`flex items-center gap-1.5 rounded-md px-1 py-1 text-left text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-60 ${
                  focused === i ? 'bg-muted' : ''
                } ${selected ? 'text-foreground' : 'text-foreground/70 hover:text-foreground'}`}
              >
                {rowMarker(i)}
                {boxMarker(selected, q.multi_select)}
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
            onMouseEnter={() => setFocused(otherIndex)}
            onClick={() => {
              setFocused(otherIndex);
              setOtherOpen((p) => ({ ...p, [active]: !p[active] }));
            }}
            className={`flex items-center gap-1.5 rounded-md px-1 py-1 text-left text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-60 ${
              focused === otherIndex ? 'bg-muted' : ''
            } ${otherOpen[active] ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
          >
            {rowMarker(otherIndex)}
            <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-[3px] border border-dashed border-muted-foreground/40" />
            {t('clarify.other')}
          </button>
        </div>
        {otherOpen[active] && (
          <input
            ref={otherInputRef}
            type="text"
            value={others[active] ?? ''}
            disabled={disabled}
            onChange={(e) => setOthers((p) => ({ ...p, [active]: e.target.value }))}
            onKeyDown={(e) => {
              // keep card-level keys working; let typing pass through untouched
              if (e.key === 'Enter') { e.preventDefault(); if (allAnswered) handleSend(); }
              e.stopPropagation();
            }}
            placeholder={t('clarify.otherPlaceholder')}
            className="mt-1.5 ml-7 w-[calc(100%-1.75rem)] rounded-md border border-border bg-background px-2.5 py-1 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/50"
          />
        )}
      </div>

      <div className="flex items-center justify-between gap-2 px-3 pb-2.5 pt-1">
        <span className="text-[10px] text-muted-foreground/50 select-none">
          {t('clarify.keysHint')}
        </span>
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !allAnswered}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-default cursor-pointer"
        >
          <Send className="w-3 h-3" />
          {t('clarify.send')}
        </button>
      </div>
    </motion.div>
  );
}
