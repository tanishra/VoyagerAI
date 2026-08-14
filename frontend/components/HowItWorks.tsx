'use client';

import { motion } from 'framer-motion';
import { Compass, Sparkles, Map } from 'lucide-react';
import { useTranslations } from 'next-intl';

const steps = [
  {
    number: 1,
    title: 'Tell Us Your Preferences',
    desc: 'Enter your destination, budget, travel style, and group size. Optional dietary and constraint fields let you customize further.',
    icon: Compass,
    gradient: 'from-indigo-500/10 to-blue-500/10',
    border: 'border-indigo-500/15',
    textColor: 'text-indigo-600',
  },
  {
    number: 2,
    title: 'AI Generates Your Itinerary',
    desc: 'AI creates a complete day-by-day plan with activities, transport, accommodation, and cost breakdown — all within your budget.',
    icon: Sparkles,
    gradient: 'from-violet-500/10 to-purple-500/10',
    border: 'border-violet-500/15',
    textColor: 'text-violet-600',
  },
  {
    number: 3,
    title: 'Explore & Customize',
    desc: 'Review your itinerary, check budget status, get local tips, and replan any day that doesn\'t fit your vision.',
    icon: Map,
    gradient: 'from-emerald-500/10 to-teal-500/10',
    border: 'border-emerald-500/15',
    textColor: 'text-emerald-600',
  },
];

export default function HowItWorks() {
  const t = useTranslations('home');
  return (
    <section className="relative py-20 md:py-28 overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] bg-gradient-to-br from-indigo-400/5 via-violet-400/5 to-emerald-400/5 rounded-full blur-3xl" />
        <div className="absolute top-0 left-1/4 right-1/4 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
      </div>

      <div className="max-w-5xl mx-auto px-4 relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-muted border border-border text-xs font-medium text-muted-foreground mb-5 tracking-wider uppercase"
          >
            <Sparkles className="w-3 h-3" />
            {t('howBadge')}
          </motion.div>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground mb-4 leading-tight tracking-tight">
            {t('howTitle')}
          </h2>
          <p className="text-muted-foreground max-w-xl mx-auto text-sm md:text-base">
            {t('howSubtitle')}
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              whileHover={{ y: -8, transition: { duration: 0.15 } }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.5, delay: i * 0.1, ease: 'easeOut' }}
              className="group relative"
            >
              <div className={`absolute -inset-2 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-2xl bg-gradient-to-br ${step.gradient}`} />

              <div className={`relative h-full p-6 rounded-2xl bg-gradient-to-br ${step.gradient} border ${step.border} backdrop-blur-xl cursor-default overflow-hidden bg-card/80`}>
                <div className="flex items-start justify-between mb-5">
                  <div className={`flex items-center justify-center w-10 h-10 rounded-full border ${step.border} bg-card group-hover:scale-110 transition-transform duration-200 shadow-sm`}>
                    <step.icon className={`w-5 h-5 ${step.textColor}`} />
                  </div>
                  <span className={`text-5xl font-black ${step.textColor} opacity-[0.08] select-none leading-none`}>
                    {String(step.number).padStart(2, '0')}
                  </span>
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-2 leading-snug">{t(`step${step.number}Title`)}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{t(`step${step.number}Desc`)}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
