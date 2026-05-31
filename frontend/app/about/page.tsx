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
          className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-2xl p-8 md:p-10 relative overflow-hidden"
        >
          <div className="absolute -top-24 -right-24 w-48 h-48 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-violet-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-gradient-to-br from-sky-500/20 to-blue-500/20 border border-sky-500/20">
                <Cpu className="w-5 h-5 text-sky-400" />
              </div>
              <h2 className="text-xl font-bold text-white">How It Works — Behind the Scenes</h2>
            </div>

            <div className="p-4 rounded-xl bg-white/[0.03] border border-white/5 mb-8">
              <p className="text-sm text-white/60 leading-relaxed">
                When you submit your trip preferences, our backend uses Google&apos;s Gemini through
                a structured agent workflow. The agent:
              </p>
            </div>

            <div className="relative pl-10">
              <div className="absolute left-[19px] top-1 bottom-1 w-px bg-gradient-to-b from-sky-500/30 via-amber-500/30 via-red-500/30 via-emerald-500/30 to-violet-500/30" />

              <div className="space-y-5">
                {([
                  { text: <>Generates a complete itinerary using the <code className="text-sky-400">generate_itinerary</code> tool</>, border: 'border-sky-500/20', bg: 'bg-sky-500/10', textColor: 'text-sky-400' },
                  { text: <>Validates it against your budget using <code className="text-amber-400">validate_constraints</code></>, border: 'border-amber-500/20', bg: 'bg-amber-500/10', textColor: 'text-amber-400' },
                  { text: <>If validation fails, regenerates with tighter budget guidance</>, border: 'border-red-500/20', bg: 'bg-red-500/10', textColor: 'text-red-400' },
                  { text: <>Once valid, enriches each day with local tips via <code className="text-emerald-400">enrich_day</code></>, border: 'border-emerald-500/20', bg: 'bg-emerald-500/10', textColor: 'text-emerald-400' },
                  { text: <>Returns a fully structured JSON itinerary</>, border: 'border-violet-500/20', bg: 'bg-violet-500/10', textColor: 'text-violet-400' },
                ] as const).map((step, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.4, delay: 0.1 * i }}
                    className="relative group"
                  >
                    <div className={`absolute -left-10 top-1 w-7 h-7 rounded-full border-2 flex items-center justify-center z-10 transition-all duration-200 group-hover:scale-110 ${step.border} ${step.bg}`}>
                      <span className={`text-[11px] font-bold ${step.textColor}`}>{i + 1}</span>
                    </div>
                    <div className={`ml-3 p-4 rounded-xl border transition-all duration-200 group-hover:border-white/20 group-hover:bg-white/[0.06] ${step.border} bg-white/[0.03]`}>
                      <p className="text-sm text-white/80 leading-relaxed">{step.text}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            <div className="mt-8 p-4 rounded-xl bg-gradient-to-r from-sky-500/5 to-violet-500/5 border border-white/5">
              <p className="text-sm text-white/60 leading-relaxed">
                The frontend then renders this data as a beautiful, interactive timeline with
                budget tracking, warnings, and packing essentials — all styled with a dark
                glassmorphism theme.
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
