'use client';

import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';
import ScrollProgressBar from '@/components/about/ScrollProgressBar';
import AgentArchitecture from '@/components/about/AgentArchitecture';
import WorkflowTimeline from '@/components/about/WorkflowTimeline';

export default function AboutPage() {
  const t = useTranslations('about');
  return (
    <main className="relative min-h-screen pt-24 pb-16">
      <ScrollProgressBar />

      <div className="relative z-10 max-w-4xl mx-auto px-6">
        {/* Hero section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-16"
        >
          <div className="w-12 h-px bg-primary mb-8" />
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

        {/* Outro */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mt-12 pt-8 border-t border-border"
        >
          <p className="text-sm text-muted-foreground leading-relaxed text-center">
            {t('outro')}
          </p>
        </motion.div>
      </div>
    </main>
  );
}
