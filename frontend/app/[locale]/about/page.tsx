'use client';

import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { useTranslations } from 'next-intl';
import ScrollProgressBar from '@/components/about/ScrollProgressBar';
import AgentArchitecture from '@/components/about/AgentArchitecture';
import WorkflowTimeline from '@/components/about/WorkflowTimeline';

export default function AboutPage() {
  const t = useTranslations('about');
  return (
    <main className="relative min-h-screen pt-24 pb-16">
      <ScrollProgressBar />

      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-1/4 left-1/3 w-[600px] h-[600px] bg-indigo-400/[0.06] rounded-full blur-[120px] animate-aurora" />
        <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-violet-400/[0.04] rounded-full blur-[120px] animate-float-slow" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-4">
        {/* Hero section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            {t('badge')}
          </div>
          <h1 className="text-3xl md:text-5xl font-bold text-foreground mb-4 tracking-tight">
            {t('title')}
          </h1>
          <p className="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
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
          className="mt-8 p-6 rounded-2xl bg-gradient-to-r from-indigo-500/5 to-violet-500/5 border border-border backdrop-blur-sm"
        >
          <p className="text-sm text-muted-foreground leading-relaxed text-center">
            {t('outro')}
          </p>
        </motion.div>
      </div>
    </main>
  );
}
