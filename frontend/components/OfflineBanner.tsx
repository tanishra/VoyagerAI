'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { WifiOff, Wifi, CloudUpload } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useOnlineStatus } from '@/lib/useOnlineStatus';

interface OfflineBannerProps {
  replaying?: boolean;
}

export default function OfflineBanner({ replaying = false }: OfflineBannerProps) {
  const t = useTranslations('offline');
  const isOnline = useOnlineStatus();
  const [showBackOnline, setShowBackOnline] = useState(false);
  const prevOnlineRef = useRef(true);

  useEffect(() => {
    const wasOffline = !prevOnlineRef.current;
    prevOnlineRef.current = isOnline;

    if (isOnline && wasOffline && !replaying) {
      const timer = setTimeout(() => setShowBackOnline(false), 3000);
      Promise.resolve().then(() => setShowBackOnline(true));
      return () => clearTimeout(timer);
    }
  }, [isOnline, replaying]);

  const showOffline = !isOnline;
  const showReplaying = isOnline && replaying;
  const showOnline = showBackOnline && !showReplaying && !showOffline;

  return (
    <AnimatePresence>
      {(showOffline || showReplaying || showOnline) && (
        <motion.div
          initial={{ y: -60, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -60, opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed top-16 left-1/2 -translate-x-1/2 z-50 print-hidden"
        >
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded-lg shadow-lg text-sm font-medium ${
              showOffline
                ? 'bg-amber-500/90 text-white'
                : showReplaying
                  ? 'bg-blue-500/90 text-white'
                  : 'bg-green-500/90 text-white'
            }`}
          >
            {showOffline && (
              <>
                <WifiOff className="w-4 h-4" />
                {t('offline')}
              </>
            )}
            {showReplaying && (
              <>
                <CloudUpload className="w-4 h-4 animate-pulse" />
                {t('replaying')}
              </>
            )}
            {showOnline && (
              <>
                <Wifi className="w-4 h-4" />
                {t('backOnline')}
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
