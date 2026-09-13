'use client';

import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';

interface StepDef {
  titleKey: string;
  descKey: string;
}

const steps: StepDef[] = [
  { titleKey: 'step1Title', descKey: 'step1Desc' },
  { titleKey: 'step2Title', descKey: 'step2Desc' },
  { titleKey: 'step3Title', descKey: 'step3Desc' },
  { titleKey: 'step4Title', descKey: 'step4Desc' },
  { titleKey: 'step5Title', descKey: 'step5Desc' },
  { titleKey: 'step6Title', descKey: 'step6Desc' },
  { titleKey: 'step7Title', descKey: 'step7Desc' },
  { titleKey: 'step8Title', descKey: 'step8Desc' },
  { titleKey: 'step9Title', descKey: 'step9Desc' },
  { titleKey: 'step10Title', descKey: 'step10Desc' },
  { titleKey: 'step11Title', descKey: 'step11Desc' },
  { titleKey: 'step12Title', descKey: 'step12Desc' },
  { titleKey: 'step13Title', descKey: 'step13Desc' },
];

export default function WorkflowTimeline() {
  const t = useTranslations('about');

  return (
    <section className="relative mb-20">
      <motion.div
        initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
        whileInView={{ opacity: 1, y: 0, filter: 'blur(0)' }}
        viewport={{ once: true }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="mb-10"
      >
        <p className="font-mono text-[10px] tracking-[0.25em] text-primary mb-2">SECTION 02 · PROCESS</p>
        <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-2 tracking-tight">
          {t('workflowTitle')}
        </h2>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          {t('workflowIntro')}
        </p>
      </motion.div>

      <div className="max-w-2xl mx-auto">
        {steps.map((step, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.04, ease: [0.22, 1, 0.36, 1] }}
            className="grid grid-cols-[48px_1fr] gap-5 border-b border-border last:border-b-0 py-5"
          >
            <span className="font-mono text-[13px] font-medium tracking-[0.05em] text-primary">
              {String(i + 1).padStart(2, '0')}
            </span>
            <div>
              <h4 className="text-sm font-semibold text-foreground mb-1">
                {t(step.titleKey)}
              </h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t(step.descKey)}
              </p>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
