'use client';

import { motion } from 'framer-motion';
import { Sparkles, Globe, Cpu, Zap } from 'lucide-react';

const highlights = [
  {
    title: 'Built with Next.js',
    desc: 'Modern React framework with server-side rendering, lazy loading, and optimized performance.',
    icon: Globe,
    gradient: 'from-sky-500/20 to-blue-500/20',
    border: 'border-sky-500/20',
    color: 'text-sky-400',
  },
  {
    title: 'Google Gemini',
    desc: 'Powered by Google Gemini 2.5 Pro for intelligent trip planning.',
    icon: Cpu,
    gradient: 'from-violet-500/20 to-purple-500/20',
    border: 'border-violet-500/20',
    color: 'text-violet-400',
  },
  {
    title: 'Real-time AI',
    desc: 'Itineraries generated in seconds with intelligent budget tracking and day-by-day optimization.',
    icon: Zap,
    gradient: 'from-amber-500/20 to-orange-500/20',
    border: 'border-amber-500/20',
    color: 'text-amber-400',
  },
];

export default function AboutPage() {
  return (
    <main className="relative min-h-screen pt-24 pb-16">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-1/4 left-1/3 w-[600px] h-[600px] bg-sky-500/[0.05] rounded-full blur-[120px]" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-medium mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            About
          </div>
          <h1 className="text-3xl md:text-5xl font-bold text-white mb-4">
            AI-Powered Travel Planning
          </h1>
          <p className="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            VoyagerAI combines the power of Google&apos;s Gemini with a beautiful, intuitive
            interface to create personalized travel itineraries in seconds. No more hours of
            research — just tell us where you want to go and we&apos;ll handle the rest.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6 mb-16">
          {highlights.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 * i }}
              className={`p-6 rounded-2xl bg-gradient-to-br ${item.gradient} border ${item.border}`}
            >
              <div className={`p-2.5 w-fit rounded-xl bg-white/5 border ${item.border} mb-4`}>
                <item.icon className={`w-5 h-5 ${item.color}`} />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
              <p className="text-sm text-white/60 leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-2xl p-8"
        >
          <h2 className="text-xl font-bold text-white mb-4">How It Works — Behind the Scenes</h2>
          <div className="space-y-4 text-sm text-white/60 leading-relaxed">
            <p>
              When you submit your trip preferences, our backend uses Google&apos;s Gemini through
              a structured agent workflow. The agent:
            </p>
            <ol className="space-y-2 list-decimal list-inside">
              <li>Generates a complete itinerary using the <code className="text-sky-400">generate_itinerary</code> tool</li>
              <li>Validates it against your budget using <code className="text-sky-400">validate_constraints</code></li>
              <li>If validation fails, regenerates with tighter budget guidance</li>
              <li>Once valid, enriches each day with local tips via <code className="text-sky-400">enrich_day</code></li>
              <li>Returns a fully structured JSON itinerary</li>
            </ol>
            <p>
              The frontend then renders this data as a beautiful, interactive timeline with
              budget tracking, warnings, and packing essentials — all styled with a dark
              glassmorphism theme.
            </p>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
