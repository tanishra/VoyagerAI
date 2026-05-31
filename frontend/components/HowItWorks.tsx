'use client';

import { motion } from 'framer-motion';
import { Compass, Sparkles, Map } from 'lucide-react';

const steps = [
  {
    number: 1,
    title: 'Tell Us Your Preferences',
    desc: 'Enter your destination, budget, travel style, and group size. Optional dietary and constraint fields let you customize further.',
    icon: Compass,
    gradient: 'from-sky-500/20 to-blue-500/20',
    border: 'border-sky-500/20',
    textColor: 'text-sky-400',
  },
  {
    number: 2,
    title: 'Gemini Generates Your Itinerary',
    desc: 'Gemini creates a complete day-by-day plan with activities, transport, accommodation, and cost breakdown — all within your budget.',
    icon: Sparkles,
    gradient: 'from-amber-500/20 to-orange-500/20',
    border: 'border-amber-500/20',
    textColor: 'text-amber-400',
  },
  {
    number: 3,
    title: 'Explore & Customize',
    desc: 'Review your itinerary, check budget status, get local tips, and replan any day that doesn\'t fit your vision.',
    icon: Map,
    gradient: 'from-emerald-500/20 to-teal-500/20',
    border: 'border-emerald-500/20',
    textColor: 'text-emerald-400',
  },
];

export default function HowItWorks() {
  return (
    <section className="relative py-20 md:py-28 overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] bg-gradient-to-br from-sky-500/5 via-amber-500/5 to-emerald-500/5 rounded-full blur-3xl" />
        <div className="absolute top-0 left-1/4 right-1/4 h-px bg-gradient-to-r from-transparent via-white/5 to-transparent" />
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
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/[0.04] border border-white/10 text-xs font-medium text-white/50 mb-5 tracking-wider uppercase"
          >
            <Sparkles className="w-3 h-3" />
            How it works
          </motion.div>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 leading-tight">
            Three Steps to Your Perfect Trip
          </h2>
          <p className="text-muted-foreground max-w-xl mx-auto text-sm md:text-base">
            From your preferences to a complete itinerary in minutes
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

              <div className={`relative h-full p-6 rounded-2xl bg-gradient-to-br ${step.gradient} border ${step.border} backdrop-blur-xl cursor-default overflow-hidden`}>
                <div className="flex items-start justify-between mb-5">
                  <div className={`flex items-center justify-center w-10 h-10 rounded-full border ${step.border} bg-white/[0.04] group-hover:scale-110 transition-transform duration-200`}>
                    <step.icon className={`w-5 h-5 ${step.textColor}`} />
                  </div>
                  <span className={`text-5xl font-black ${step.textColor} opacity-[0.07] select-none leading-none`}>
                    {String(step.number).padStart(2, '0')}
                  </span>
                </div>

                <h3 className="text-lg font-semibold text-white mb-2 leading-snug">{step.title}</h3>
                <p className="text-sm text-white/60 leading-relaxed">{step.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
