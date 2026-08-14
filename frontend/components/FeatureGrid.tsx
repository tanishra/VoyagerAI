'use client';

import { motion } from 'framer-motion';
import { Sparkles, DollarSign, Calendar, Lightbulb, Luggage, RefreshCw } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { SpotlightCard } from '@/components/ui/spotlight-card';

const features = [
  {
    title: 'AI-Powered Planning',
    desc: 'AI generates personalized itineraries based on your preferences, budget, and travel style.',
    icon: Sparkles,
    gradient: 'from-indigo-500/10 to-blue-500/10',
    border: 'border-indigo-500/15',
    textColor: 'text-indigo-600',
  },
  {
    title: 'Budget Tracking',
    desc: 'Real-time budget gauge shows you exactly where you stand — within, over, or under budget.',
    icon: DollarSign,
    gradient: 'from-emerald-500/10 to-teal-500/10',
    border: 'border-emerald-500/15',
    textColor: 'text-emerald-600',
  },
  {
    title: 'Day-by-Day Plans',
    desc: 'Every day is broken into morning, afternoon, and evening with activities, costs, and durations.',
    icon: Calendar,
    gradient: 'from-violet-500/10 to-purple-500/10',
    border: 'border-violet-500/15',
    textColor: 'text-violet-600',
  },
  {
    title: 'Local Tips',
    desc: 'Get practical advice on weather, customs, safety, and money-saving tips for each activity.',
    icon: Lightbulb,
    gradient: 'from-amber-500/10 to-yellow-500/10',
    border: 'border-amber-500/15',
    textColor: 'text-amber-600',
  },
  {
    title: 'Packing Essentials',
    desc: 'AI-crafted packing lists tailored to your destination, season, and planned activities.',
    icon: Luggage,
    gradient: 'from-cyan-500/10 to-blue-500/10',
    border: 'border-cyan-500/15',
    textColor: 'text-cyan-600',
  },
  {
    title: 'Replan Any Day',
    desc: 'Not happy with a day? Replan it with a custom request and AI will adjust on the fly.',
    icon: RefreshCw,
    gradient: 'from-rose-500/10 to-pink-500/10',
    border: 'border-rose-500/15',
    textColor: 'text-rose-600',
  },
];

export default function FeatureGrid() {
  const t = useTranslations('home');
  return (
    <section className="py-20 md:py-28 border-t border-border">
      <div className="max-w-5xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-3 tracking-tight">
            {t('featuresTitle')}
          </h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            {t('featuresSubtitle')}
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.5, delay: i * 0.05 }}
              whileHover={{ y: -4, transition: { duration: 0.2 } }}
              className={`p-5 rounded-xl bg-gradient-to-br ${feature.gradient} border ${feature.border} group cursor-default bg-card/80 backdrop-blur-sm hover:shadow-lg transition-shadow duration-300 relative overflow-hidden`}
            >
              <SpotlightCard className="absolute inset-0 rounded-xl" spotlightColor="rgba(99, 102, 241, 0.06)" />
              <div className={`p-2 w-fit rounded-lg bg-card border ${feature.border} mb-3 group-hover:scale-110 transition-transform duration-200 shadow-sm`}>
                <feature.icon className={`w-4 h-4 ${feature.textColor}`} />
              </div>
              <h3 className="text-sm font-semibold text-foreground mb-1.5">{t(`f${i + 1}Title`)}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{t(`f${i + 1}Desc`)}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
