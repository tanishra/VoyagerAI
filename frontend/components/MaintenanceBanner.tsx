'use client';

import { useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Wrench } from 'lucide-react';

export default function MaintenanceBanner() {
  const t = useTranslations('maintenance');

  useEffect(() => {
    const prev = document.body.style.paddingTop;
    document.body.style.paddingTop = '2.5rem';
    return () => {
      document.body.style.paddingTop = prev;
    };
  }, []);

  return (
    <div
      role="alert"
      className="fixed top-0 inset-x-0 z-[60] flex h-10 items-center justify-center gap-2 px-4 text-sm bg-amber-500/15 border-b border-amber-500/30 text-amber-900 dark:text-amber-200 backdrop-blur-sm"
    >
      <Wrench className="w-4 h-4 shrink-0" aria-hidden />
      <p className="text-center">{t('message')}</p>
    </div>
  );
}
