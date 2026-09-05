'use client';

import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { getLoginUrl } from '@/lib/auth';

export default function LoginPage() {
  const t = useTranslations('auth');
  const tNav = useTranslations('nav');
  return (
    <main className="relative min-h-screen pt-16">
      <div className="relative z-10 max-w-md mx-auto px-6 pt-24 pb-12">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="text-center"
        >
          <div className="flex items-center justify-center gap-2.5 mb-8">
            <span className="w-1 h-7 bg-primary rounded-full" />
            <h1 className="text-3xl font-bold text-foreground tracking-tight">{tNav('brand')}</h1>
          </div>

          <p className="text-sm text-muted-foreground mb-10 max-w-xs mx-auto">
            {t('signInPrompt')}
          </p>

          <a
            href={getLoginUrl()}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all duration-200 hover:-translate-y-0.5 shadow-sm"
          >
            {t('signInWithGoogle')}
            <ArrowRight className="w-4 h-4" />
          </a>

          <p className="text-xs text-muted-foreground mt-6">
            {t('privacyNote')}
          </p>
        </motion.div>
      </div>
    </main>
  );
}
