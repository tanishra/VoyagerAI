'use client';

import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { useTranslations } from 'next-intl';

export default function CTASection() {
  const t = useTranslations('home');
  return (
    <section className="py-24 md:py-32 border-t border-border">
      <div className="max-w-3xl mx-auto px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
        >
          <div className="w-12 h-px bg-primary mx-auto mb-8" />
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4 tracking-tight">
            {t('ctaTitle')}
          </h2>
          <p className="text-muted-foreground mb-10 max-w-md mx-auto">
            {t('ctaDesc')}
          </p>
          <Link
            href="/chat"
            className="group inline-flex items-center gap-2 px-7 py-3.5 rounded-lg bg-primary text-primary-foreground font-semibold text-sm transition-all duration-300 hover:bg-primary/90 hover:-translate-y-0.5 shadow-sm"
          >
            {t('ctaButton')}
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
