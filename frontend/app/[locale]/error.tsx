'use client';

import { useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function LocaleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations('common');

  useEffect(() => {
    console.error('Route error:', error);
  }, [error]);

  return (
    <div
      role="alert"
      className="flex-1 flex flex-col items-center justify-center gap-4 p-8 text-center"
    >
      <div className="p-3 rounded-full bg-red-500/20">
        <AlertTriangle className="w-8 h-8 text-red-400" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-red-300 mb-1">{t('errorTitle')}</h2>
        <p className="text-sm text-red-300/70 max-w-md">{t('errorDescription')}</p>
      </div>
      <Button
        onClick={reset}
        variant="outline"
        className="border-red-500/30 text-red-300 hover:bg-red-500/10 cursor-pointer"
      >
        <RefreshCw className="w-4 h-4 mr-2" />
        {t('tryAgain')}
      </Button>
    </div>
  );
}
