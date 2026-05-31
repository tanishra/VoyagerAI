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
    <section className="py-20 md:py-28">
      <div className="max-w-5xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            How It Works
          </h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            Three simple steps to your perfect trip
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              whileHover={{ y: -4, transition: { duration: 0.15 } }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.6, delay: i * 0.15, ease: 'easeOut' }}
              className={`relative h-full p-6 rounded-2xl bg-gradient-to-br ${step.gradient} border ${step.border} backdrop-blur-xl group cursor-default`}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className={`p-2.5 rounded-xl bg-white/5 border ${step.border} group-hover:scale-110 transition-transform duration-200`}>
                  <step.icon className={`w-5 h-5 ${step.textColor}`} />
                </div>
                <span className={`text-xs font-bold ${step.textColor}`}>
                  Step {step.number}
                </span>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{step.title}</h3>
              <p className="text-sm text-white/60 leading-relaxed">{step.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
