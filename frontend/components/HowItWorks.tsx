'use client';

import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';

const steps = [
  { number: 1, title: 'step1Title', desc: 'step1Desc' },
  { number: 2, title: 'step2Title', desc: 'step2Desc' },
  { number: 3, title: 'step3Title', desc: 'step3Desc' },
];

export default function HowItWorks() {
  const t = useTranslations('home');
  return (
    <section className="relative py-24 md:py-32">
      <div className="max-w-5xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="mb-20"
        >
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground mb-4 leading-tight tracking-tight">
            {t('howTitle')}
          </h2>
          <p className="text-muted-foreground max-w-xl text-sm md:text-base">
            {t('howSubtitle')}
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-px bg-border">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="bg-background p-8 md:p-10"
            >
              <div className="text-primary text-sm font-mono mb-4 tracking-wider">
                {String(step.number).padStart(2, '0')}
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-3 leading-snug">
                {t(step.title)}
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t(step.desc)}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
