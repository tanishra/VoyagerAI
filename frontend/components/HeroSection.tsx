'use client';

import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { useTranslations } from 'next-intl';

export default function HeroSection() {
  const t = useTranslations('home');
  return (
    <section className="flex flex-col md:flex-row min-h-[92vh] pt-16">
      {/* Left: full-bleed destination photograph */}
      <div className="relative w-full md:w-1/2 min-h-[40vh] md:min-h-[92vh] overflow-hidden">
        <Image
          src="/destinations/kyoto-autumn.webp"
          alt="Kyoto autumn temple"
          fill
          priority
          sizes="(max-width: 768px) 100vw, 50vw"
          className="object-cover"
        />
      </div>

      {/* The gutter seam — cinnabar hairline rule */}
      <div className="hidden md:block w-px bg-primary/40 shrink-0" />

      {/* Right: editorial text */}
      <div className="flex-1 flex items-center">
        <div className="px-6 md:px-12 lg:px-16 py-16 md:py-24 flex flex-col justify-center w-full max-w-xl md:ml-auto">
          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
            className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold leading-[1.05] mb-6 tracking-tight text-foreground"
          >
            {t('heroLine1')}
            <br />
            <span className="text-primary italic font-semibold">
              {t('heroLine2')}
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="text-base sm:text-lg text-muted-foreground max-w-md mb-10 leading-relaxed"
          >
            {t('heroDesc')}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col sm:flex-row items-start sm:items-center gap-4"
          >
            <Link
              href="/chat"
              className="group inline-flex items-center gap-2 px-7 py-3.5 rounded-lg bg-primary text-primary-foreground font-semibold text-sm transition-all duration-300 hover:bg-primary/90 hover:-translate-y-0.5 shadow-sm"
            >
              {t('planYourTrip')}
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <Link
              href="/about"
              className="inline-flex items-center gap-2 text-sm font-medium text-foreground/70 hover:text-primary transition-colors duration-200"
            >
              {t('howItWorks')}
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 0.7 }}
            className="mt-14 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground"
          >
            <span className="flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-primary" />
              {t('aiGenerated')}
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-primary" />
              {t('budgetTracking')}
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-primary" />
              {t('dayByDay')}
            </span>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
