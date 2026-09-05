'use client';

import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';

const features = [
  { num: '01', titleKey: 'f1Title', descKey: 'f1Desc' },
  { num: '02', titleKey: 'f2Title', descKey: 'f2Desc' },
  { num: '03', titleKey: 'f3Title', descKey: 'f3Desc' },
  { num: '04', titleKey: 'f4Title', descKey: 'f4Desc' },
  { num: '05', titleKey: 'f5Title', descKey: 'f5Desc' },
  { num: '06', titleKey: 'f6Title', descKey: 'f6Desc' },
];

export default function FeatureGrid() {
  const t = useTranslations('home');
  return (
    <section className="py-24 md:py-32 border-t border-border">
      <div className="max-w-5xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="mb-16"
        >
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-3 tracking-tight">
            {t('featuresTitle')}
          </h2>
          <p className="text-muted-foreground max-w-lg">
            {t('featuresSubtitle')}
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 gap-px bg-border">
          {features.map((feature, i) => (
            <motion.div
              key={feature.num}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.4, delay: (i % 2) * 0.1 }}
              className="bg-background p-8 md:p-10 group"
            >
              <div className="text-primary text-xs font-mono mb-3 tracking-wider">
                {feature.num}
              </div>
              <h3 className="text-base font-semibold text-foreground mb-2">
                {t(feature.titleKey)}
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t(feature.descKey)}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
