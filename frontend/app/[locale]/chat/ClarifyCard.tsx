'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Check, Send } from 'lucide-react';
import { useTranslations } from 'next-intl';
import type { ClarifyData, ClarifyQuestion } from '@/lib/types';

function optionKey(field: string, label: string, value?: string): string {
  return `clarifyOptions.${field}.${(value ?? label).toLowerCase().replace(/\s+/g, '_')}`;
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
  // selections[i] = set of chosen option labels for question i, or Other text
  const [selections, setSelections] = useState<Record<number, Set<string>>>({});
  const [others, setOthers] = useState<Record<number, string>>({});
  const [otherOpen, setOtherOpen] = useState<Record<number, boolean>>({});

  const questions = data.questions ?? [];

  const localized = (q: ClarifyQuestion, label: string, value?: string): string => {
    try {
      const key = optionKey(q.field, label, value);
      const translated = t(key);
      return translated === key ? label : translated;
    } catch {
      return label;
    }
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

  const allAnswered =
    questions.length > 0 && questions.every((q, i) => answerFor(i, q).length > 0);

  const handleSend = () => {
    if (!allAnswered) return;
    const text = questions
      .map((q, i) => `${q.header}: ${answerFor(i, q).join(', ')}`)
      .join('; ');
    onSend(text);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="mt-3 rounded-xl border border-border bg-card overflow-hidden shadow-sm"
    >
      <div className="p-4 space-y-4">
        {questions.map((q, qi) => (
          <div key={qi} role="group" aria-label={q.question}>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {q.header}
              </span>
              <span className="text-[10px] text-muted-foreground/60">
                {q.multi_select ? t('clarify.pickMany') : t('clarify.pickOne')}
              </span>
            </div>
            <p className="text-sm text-foreground mb-2">{q.question}</p>
            <div className="flex flex-wrap gap-2">
              {q.options.map((opt) => {
                const selected = selections[qi]?.has(opt.label) ?? false;
                return (
                  <button
                    key={opt.label}
                    type="button"
                    disabled={disabled}
                    aria-pressed={selected}
                    title={opt.description}
                    onClick={() => toggle(qi, opt.label, q.multi_select)}
                    className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-60 ${
                      selected
                        ? 'border-primary/50 bg-primary/10 text-foreground'
                        : 'border-border bg-transparent text-foreground/70 hover:border-primary/40 hover:text-foreground'
                    }`}
                  >
                    {selected && <Check className="w-3 h-3 text-primary" />}
                    {localized(q, opt.label, opt.value)}
                  </button>
                );
              })}
              <button
                type="button"
                disabled={disabled}
                aria-pressed={otherOpen[qi] ?? false}
                onClick={() => setOtherOpen((p) => ({ ...p, [qi]: !p[qi] }))}
                className={`inline-flex items-center rounded-lg border px-3 py-1.5 text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-60 ${
                  otherOpen[qi]
                    ? 'border-primary/50 bg-primary/10 text-foreground'
                    : 'border-dashed border-border text-muted-foreground hover:border-primary/40 hover:text-foreground'
                }`}
              >
                {t('clarify.other')}
              </button>
            </div>
            {otherOpen[qi] && (
              <input
                type="text"
                value={others[qi] ?? ''}
                disabled={disabled}
                onChange={(e) => setOthers((p) => ({ ...p, [qi]: e.target.value }))}
                placeholder={t('clarify.otherPlaceholder')}
                className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/50"
              />
            )}
          </div>
        ))}
      </div>
      <div className="px-4 pb-4">
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !allAnswered}
          className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-default cursor-pointer"
        >
          <Send className="w-3 h-3" />
          {t('clarify.send')}
        </button>
      </div>
    </motion.div>
  );
}
