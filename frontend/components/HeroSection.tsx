'use client';

import { motion } from 'framer-motion';
import { Sparkles, ArrowRight, Globe } from 'lucide-react';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { TextGenerate } from '@/components/ui/text-generate';

export default function HeroSection() {
  const t = useTranslations('home');
  return (
    <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden pt-16">
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/3 w-[700px] h-[700px] bg-indigo-400/[0.07] rounded-full blur-[140px] animate-aurora" />
        <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-violet-400/[0.05] rounded-full blur-[120px] animate-float-slow" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[400px] bg-blue-300/[0.04] rounded-full blur-[160px]" />
      </div>

      <div
        className="absolute inset-0 pointer-events-none opacity-[0.015]"
        style={{
          backgroundImage: `linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />

      <div className="relative z-10 max-w-4xl mx-auto px-4 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="mb-6"
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-8">
            <Sparkles className="w-3.5 h-3.5" />
            {t('badge')}
          </div>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
          className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold leading-tight mb-6 tracking-tight"
        >
          <span className="bg-gradient-to-r from-foreground via-foreground/90 to-foreground/70 bg-clip-text text-transparent">
            {t('heroLine1')}
          </span>
          <br />
          <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-blue-600 bg-clip-text text-transparent">
            {t('heroLine2')}
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed"
        >
          <TextGenerate text={t('heroDesc')} duration={1} delay={0.4} />
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.45, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <Link
            href="/chat"
            className="group inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold text-sm shadow-lg shadow-indigo-500/20 transition-all duration-300 hover:shadow-xl hover:shadow-indigo-500/30 hover:-translate-y-0.5 hover:scale-105"
          >
            <Globe className="w-4 h-4" />
            {t('planYourTrip')}
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </Link>
          <Link
            href="/about"
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl border border-border bg-card text-foreground/70 hover:text-foreground hover:border-primary/30 text-sm font-medium transition-all duration-300 hover:scale-105 hover:shadow-md"
          >
            {t('howItWorks')}
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 0.7 }}
          className="mt-16 flex items-center justify-center gap-8 text-xs text-muted-foreground"
        >
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            {t('aiGenerated')}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            {t('budgetTracking')}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            {t('dayByDay')}
          </span>
        </motion.div>
      </div>
    </section>
  );
}
