'use client';

import { motion } from 'framer-motion';
import { Sparkles, DollarSign, Calendar, Lightbulb, Luggage, RefreshCw } from 'lucide-react';

const features = [
  {
    title: 'Gemini-Powered Planning',
    desc: 'Gemini generates personalized itineraries based on your preferences, budget, and travel style.',
    icon: Sparkles,
    gradient: 'from-sky-500/20 to-blue-500/20',
    border: 'border-sky-500/20',
    textColor: 'text-sky-400',
  },
  {
    title: 'Budget Tracking',
    desc: 'Real-time budget gauge shows you exactly where you stand — within, over, or under budget.',
    icon: DollarSign,
    gradient: 'from-emerald-500/20 to-teal-500/20',
    border: 'border-emerald-500/20',
    textColor: 'text-emerald-400',
  },
  {
    title: 'Day-by-Day Plans',
    desc: 'Every day is broken into morning, afternoon, and evening with activities, costs, and durations.',
    icon: Calendar,
    gradient: 'from-violet-500/20 to-purple-500/20',
    border: 'border-violet-500/20',
    textColor: 'text-violet-400',
  },
  {
    title: 'Local Tips',
    desc: 'Get practical advice on weather, customs, safety, and money-saving tips for each activity.',
    icon: Lightbulb,
    gradient: 'from-amber-500/20 to-yellow-500/20',
    border: 'border-amber-500/20',
    textColor: 'text-amber-400',
  },
  {
    title: 'Packing Essentials',
    desc: 'Gemini-crafted packing lists tailored to your destination, season, and planned activities.',
    icon: Luggage,
    gradient: 'from-cyan-500/20 to-blue-500/20',
    border: 'border-cyan-500/20',
    textColor: 'text-cyan-400',
  },
  {
    title: 'Replan Any Day',
    desc: 'Not happy with a day? Replan it with a custom request and Gemini will adjust on the fly.',
    icon: RefreshCw,
    gradient: 'from-rose-500/20 to-pink-500/20',
    border: 'border-rose-500/20',
    textColor: 'text-rose-400',
  },
];

export default function FeatureGrid() {
  return (
    <section className="py-20 md:py-28 border-t border-white/5">
      <div className="max-w-5xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            Everything You Need
          </h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            Powerful features to make trip planning effortless
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
              className={`p-5 rounded-xl bg-gradient-to-br ${feature.gradient} border ${feature.border} group cursor-default`}
            >
              <div className={`p-2 w-fit rounded-lg bg-white/5 border ${feature.border} mb-3 group-hover:scale-110 transition-transform duration-200`}>
                <feature.icon className={`w-4 h-4 ${feature.textColor}`} />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1.5">{feature.title}</h3>
              <p className="text-xs text-white/60 leading-relaxed">{feature.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
