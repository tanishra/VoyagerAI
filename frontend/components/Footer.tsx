'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { useLocale } from '@/lib/useLocale';

function LiveClock() {
  const [time, setTime] = useState<string>('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }));
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return <span className="tabular-nums">{time}</span>;
}

export default function Footer() {
  const tNav = useTranslations('nav');
  const locale = useLocale();
  return (
    <footer className="border-t border-border">
      <div className="max-w-6xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between">
          <Link
            href={`/${locale}`}
            className="flex items-center gap-2.5 text-sm font-bold text-foreground hover:text-primary transition-colors tracking-tight"
          >
            <span className="w-1 h-4 bg-primary rounded-full" />
            {tNav('brand')}
          </Link>
          <p className="text-xs text-muted-foreground/50 font-mono tracking-wide">
            <LiveClock />
          </p>
        </div>
      </div>
    </footer>
  );
}
