'use client';

import { useRef } from 'react';
import { motion, useScroll, useTransform, useSpring } from 'framer-motion';
import { useTranslations } from 'next-intl';

interface StepDef {
  titleKey: string;
  descKey: string;
  border: string;
  bg: string;
  textColor: string;
  dotBg: string;
}

const steps: StepDef[] = [
  {
    titleKey: 'step1Title',
    descKey: 'step1Desc',
    border: 'border-indigo-500/20',
    bg: 'bg-indigo-500/10',
    textColor: 'text-indigo-600',
    dotBg: 'bg-indigo-500',
  },
  {
    titleKey: 'step2Title',
    descKey: 'step2Desc',
    border: 'border-indigo-500/20',
    bg: 'bg-indigo-500/10',
    textColor: 'text-indigo-600',
    dotBg: 'bg-indigo-500',
  },
  {
    titleKey: 'step3Title',
    descKey: 'step3Desc',
    border: 'border-amber-500/20',
    bg: 'bg-amber-500/10',
    textColor: 'text-amber-600',
    dotBg: 'bg-amber-500',
  },
  {
    titleKey: 'step4Title',
    descKey: 'step4Desc',
    border: 'border-amber-500/20',
    bg: 'bg-amber-500/10',
    textColor: 'text-amber-600',
    dotBg: 'bg-amber-500',
  },
  {
    titleKey: 'step5Title',
    descKey: 'step5Desc',
    border: 'border-amber-500/20',
    bg: 'bg-amber-500/10',
    textColor: 'text-amber-600',
    dotBg: 'bg-amber-500',
  },
  {
    titleKey: 'step6Title',
    descKey: 'step6Desc',
    border: 'border-amber-500/20',
    bg: 'bg-amber-500/10',
    textColor: 'text-amber-600',
    dotBg: 'bg-amber-500',
  },
  {
    titleKey: 'step7Title',
    descKey: 'step7Desc',
    border: 'border-emerald-500/20',
    bg: 'bg-emerald-500/10',
    textColor: 'text-emerald-600',
    dotBg: 'bg-emerald-500',
  },
  {
    titleKey: 'step8Title',
    descKey: 'step8Desc',
    border: 'border-emerald-500/20',
    bg: 'bg-emerald-500/10',
    textColor: 'text-emerald-600',
    dotBg: 'bg-emerald-500',
  },
  {
    titleKey: 'step9Title',
    descKey: 'step9Desc',
    border: 'border-violet-500/20',
    bg: 'bg-violet-500/10',
    textColor: 'text-violet-600',
    dotBg: 'bg-violet-500',
  },
  {
    titleKey: 'step10Title',
    descKey: 'step10Desc',
    border: 'border-violet-500/20',
    bg: 'bg-violet-500/10',
    textColor: 'text-violet-600',
    dotBg: 'bg-violet-500',
  },
  {
    titleKey: 'step11Title',
    descKey: 'step11Desc',
    border: 'border-violet-500/20',
    bg: 'bg-violet-500/10',
    textColor: 'text-violet-600',
    dotBg: 'bg-violet-500',
  },
  {
    titleKey: 'step12Title',
    descKey: 'step12Desc',
    border: 'border-violet-500/20',
    bg: 'bg-violet-500/10',
    textColor: 'text-violet-600',
    dotBg: 'bg-violet-500',
  },
  {
    titleKey: 'step13Title',
    descKey: 'step13Desc',
    border: 'border-violet-500/20',
    bg: 'bg-violet-500/10',
    textColor: 'text-violet-600',
    dotBg: 'bg-violet-500',
  },
];

export default function WorkflowTimeline() {
  const t = useTranslations('about');
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start center', 'end center'],
  });

  const lineScaleY = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    mass: 0.3,
  });

  return (
    <section className="relative mb-20">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="text-center mb-10"
      >
        <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-3 tracking-tight">
          {t('workflowTitle')}
        </h2>
        <p className="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          {t('workflowIntro')}
        </p>
      </motion.div>

      <div
        ref={containerRef}
        className="relative max-w-3xl mx-auto pl-10 md:pl-0"
      >
        {/* Scroll-linked progress line */}
        <div className="absolute left-[19px] md:left-1/2 top-0 bottom-0 w-px bg-border md:-translate-x-1/2">
          <motion.div
            style={{ scaleY: lineScaleY, transformOrigin: '0% 0%' }}
            className="w-full h-full bg-gradient-to-b from-indigo-500 via-amber-500 via-emerald-500 to-violet-500"
          />
        </div>

        <div className="space-y-6">
          {steps.map((step, i) => {
            const isLeft = i % 2 === 0;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: isLeft ? -30 : 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ duration: 0.4, delay: 0.05 }}
                className={`relative flex items-start gap-4 ${
                  isLeft ? '' : 'md:flex-row-reverse'
                }`}
              >
                {/* Numbered dot */}
                <div
                  className={`absolute -left-10 md:left-1/2 top-1 w-8 h-8 rounded-full border-2 flex items-center justify-center z-10 md:-translate-x-1/2 transition-all duration-200 ${step.border} ${step.bg} backdrop-blur-sm`}
                >
                  <span className={`text-[11px] font-bold ${step.textColor}`}>
                    {i + 1}
                  </span>
                </div>

                {/* Card */}
                <div
                  className={`flex-1 md:max-w-[calc(50%-2rem)] ${isLeft ? 'md:pr-8' : 'md:pl-8'}`}
                >
                  <div
                    className={`p-4 rounded-xl border ${step.border} bg-card/80 backdrop-blur-sm transition-all duration-200 hover:shadow-md`}
                  >
                    <h3 className="text-sm font-semibold text-foreground mb-1">
                      {t(step.titleKey)}
                    </h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {t(step.descKey)}
                    </p>
                  </div>
                </div>

                {/* Spacer for alternating layout on desktop */}
                <div className="hidden md:block flex-1" />
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
