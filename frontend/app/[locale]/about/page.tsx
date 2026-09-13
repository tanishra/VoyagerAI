'use client';

import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import AgentArchitecture from '@/components/about/AgentArchitecture';
import WorkflowTimeline from '@/components/about/WorkflowTimeline';

export default function AboutPage() {
  const t = useTranslations('about');
  return (
    <main className="relative min-h-screen pt-24 pb-16">
      <div className="relative z-10 max-w-4xl mx-auto px-6">
        {/* Hero section */}
        <motion.div
          initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0)' }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="mb-16"
        >
          <span
            className="inline-block border-2 border-primary px-3.5 py-1 font-mono text-[11px] font-bold tracking-[0.15em] text-primary mb-6"
            style={{ transform: 'rotate(-2deg)' }}
          >
            {t('badge')}
          </span>
          <h1 className="text-3xl md:text-5xl font-bold text-foreground mb-4 tracking-tight">
            {t('title')}
          </h1>
          <p className="text-muted-foreground max-w-2xl leading-relaxed">
            {t('subtitle')}
          </p>
        </motion.div>

        {/* Agent Architecture */}
        <AgentArchitecture />

        {/* Workflow Timeline */}
        <WorkflowTimeline />

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="mt-12 pt-8 border-t border-border text-center"
        >
          <div className="w-12 h-px bg-primary mx-auto mb-5" />
          <h3 className="text-2xl font-bold tracking-tight text-foreground mb-3">
            {t('aboutCtaTitle')}
          </h3>
          <p className="text-sm text-muted-foreground mb-6">
            {t('aboutCtaDesc')}
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all duration-200 hover:-translate-y-0.5 shadow-sm"
          >
            {t('aboutCtaButton')}
            <span aria-hidden>→</span>
          </Link>
        </motion.div>
      </div>
    </main>
  );
}
