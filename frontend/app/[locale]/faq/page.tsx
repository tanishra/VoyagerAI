'use client';

import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { useTranslations } from 'next-intl';
import FaqSection from '@/components/FaqSection';

export default function FaqPage() {
  const t = useTranslations('faq');
  return (
    <main className="relative min-h-screen pt-24 pb-16">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-violet-400/[0.05] rounded-full blur-[100px] animate-float-slow" />
      </div>

      <div className="relative z-10 max-w-3xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            {t('badge')}
          </div>
          <h1 className="text-3xl md:text-5xl font-bold text-foreground mb-4 tracking-tight">
            {t('title')}
          </h1>
          <p className="text-muted-foreground max-w-xl mx-auto">
            {t('subtitle')}
          </p>
        </motion.div>

        <FaqSection />
      </div>
    </main>
  );
}
