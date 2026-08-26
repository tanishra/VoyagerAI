'use client';

import { useState, useEffect, useMemo, type RefObject } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Send, Compass, UtensilsCrossed, Users, Wallet, Crown, Landmark } from 'lucide-react';

type TranslationFunc = (key: string) => string;

interface SuggestionPromptsProps {
  onSend: (overrideText?: string) => void;
  input: string;
  setInput: (val: string) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  handleKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  t: TranslationFunc;
}

const CATEGORIES = [
  { id: 'adventure', icon: Compass },
  { id: 'food', icon: UtensilsCrossed },
  { id: 'family', icon: Users },
  { id: 'budget', icon: Wallet },
  { id: 'luxury', icon: Crown },
  { id: 'cultural', icon: Landmark },
] as const;

const SUGGESTION_COUNT = 4;

function pickRandom<T>(arr: T[], count: number): T[] {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, count);
}

export default function SuggestionPrompts({
  onSend,
  input,
  setInput,
  inputRef,
  handleKeyDown,
  t,
}: SuggestionPromptsProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('adventure');

  const allSuggestions = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const cat of CATEGORIES) {
      map[cat.id] = [
        t(`cat${cat.id.charAt(0).toUpperCase()}${cat.id.slice(1)}Suggestion1`),
        t(`cat${cat.id.charAt(0).toUpperCase()}${cat.id.slice(1)}Suggestion2`),
        t(`cat${cat.id.charAt(0).toUpperCase()}${cat.id.slice(1)}Suggestion3`),
        t(`cat${cat.id.charAt(0).toUpperCase()}${cat.id.slice(1)}Suggestion4`),
        t(`cat${cat.id.charAt(0).toUpperCase()}${cat.id.slice(1)}Suggestion5`),
        t(`cat${cat.id.charAt(0).toUpperCase()}${cat.id.slice(1)}Suggestion6`),
      ];
    }
    return map;
  }, [t]);

  const [displayedSuggestions, setDisplayedSuggestions] = useState<string[]>([]);

  useEffect(() => {
    const pool = allSuggestions[selectedCategory] ?? [];
    setDisplayedSuggestions(pickRandom(pool, SUGGESTION_COUNT));
  }, [selectedCategory, allSuggestions]);

  const selectedCat = CATEGORIES.find((c) => c.id === selectedCategory)!;

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 relative">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center w-full max-w-2xl"
      >
        <div className="p-3.5 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-violet-500/10 border border-indigo-500/15 mb-5">
          <Sparkles className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-2xl font-semibold text-foreground mb-2">{t('greeting')}</h1>
        <p className="text-sm text-muted-foreground max-w-lg text-center mb-6">{t('subtitle')}</p>

        {/* Category pills */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-6">
          {CATEGORIES.map((cat) => {
            const isActive = cat.id === selectedCategory;
            const CatIcon = cat.icon;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                  isActive
                    ? 'bg-primary text-primary-foreground border border-primary'
                    : 'bg-card text-muted-foreground border border-border hover:border-primary/30 hover:text-foreground'
                }`}
                aria-pressed={isActive}
              >
                <CatIcon className="w-3.5 h-3.5" />
                {t(`cat${cat.id.charAt(0).toUpperCase()}${cat.id.slice(1)}`)}
              </button>
            );
          })}
        </div>

        {/* Suggestion grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mb-8">
          {displayedSuggestions.map((text, i) => (
            <button
              key={`${selectedCategory}-${i}`}
              onClick={() => onSend(text)}
              className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all text-left cursor-pointer"
            >
              <selectedCat.icon className="w-4 h-4 text-primary shrink-0" />
              <span className="text-sm text-foreground/80">{text}</span>
            </button>
          ))}
        </div>

        {/* Centered input bar */}
        <div className="w-full">
          <div className="flex items-center gap-2 rounded-2xl border border-border bg-card shadow-sm px-4 py-3 focus-within:border-primary/40 focus-within:shadow-md transition-all">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('placeholder')}
              rows={1}
              aria-label={t('messageInput')}
              className="flex-1 bg-transparent border-0 text-sm text-foreground placeholder:text-muted-foreground/50 resize-none outline-none focus:ring-0 transition-colors max-h-32 leading-6"
            />
            <button
              onClick={() => onSend()}
              disabled={!input.trim()}
              className="shrink-0 p-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              aria-label={t('send')}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground/40 mt-2 text-center">
            {t('enterToSend')}
          </p>
        </div>
      </motion.div>
    </div>
  );
}
