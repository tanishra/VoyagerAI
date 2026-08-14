'use client';

import { motion } from 'framer-motion';
import { Sparkles, Globe, Cpu, Zap } from 'lucide-react';
import { useTranslations } from 'next-intl';

const highlights = [
  {
    title: 'Built with Next.js',
    desc: 'Modern React framework with server-side rendering, lazy loading, and optimized performance.',
    icon: Globe,
    gradient: 'from-indigo-500/10 to-blue-500/10',
    border: 'border-indigo-500/15',
    color: 'text-indigo-600',
  },
  {
    title: 'Multi-Provider AI',
    desc: 'Powered by LiteLLM for dynamic switching between Gemini, OpenAI, Anthropic, and more.',
    icon: Cpu,
    gradient: 'from-violet-500/10 to-purple-500/10',
    border: 'border-violet-500/15',
    color: 'text-violet-600',
  },
  {
    title: 'Real-time AI',
    desc: 'Itineraries generated in seconds with intelligent budget tracking and day-by-day optimization.',
    icon: Zap,
    gradient: 'from-amber-500/10 to-orange-500/10',
    border: 'border-amber-500/15',
    color: 'text-amber-600',
  },
];

export default function AboutPage() {
  const t = useTranslations('about');
  return (
    <main className="relative min-h-screen pt-24 pb-16">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-1/4 left-1/3 w-[600px] h-[600px] bg-indigo-400/[0.06] rounded-full blur-[120px] animate-aurora" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            {t('badge')}
          </div>
          <h1 className="text-3xl md:text-5xl font-bold text-foreground mb-4 tracking-tight">
            {t('title')}
          </h1>
          <p className="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            {t('subtitle')}
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6 mb-16">
          {highlights.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 * i }}
              className={`p-6 rounded-2xl bg-gradient-to-br ${item.gradient} border ${item.border} bg-card/80 backdrop-blur-sm`}
            >
              <div className={`p-2.5 w-fit rounded-xl bg-card border ${item.border} mb-4 shadow-sm`}>
                <item.icon className={`w-5 h-5 ${item.color}`} />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">{t(`highlight${i + 1}Title`)}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{t(`highlight${i + 1}Desc`)}</p>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="rounded-2xl border border-border bg-card/80 backdrop-blur-2xl p-8 md:p-10 relative overflow-hidden shadow-sm"
        >
          <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-400/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-violet-400/10 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-gradient-to-br from-indigo-500/10 to-blue-500/10 border border-indigo-500/15">
                <Cpu className="w-5 h-5 text-indigo-600" />
              </div>
              <h2 className="text-xl font-bold text-foreground">{t('howItWorksTitle')}</h2>
            </div>

            <div className="p-4 rounded-xl bg-muted border border-border mb-8">
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t('howItWorksIntro')}
              </p>
            </div>

            <div className="relative pl-10">
              <div className="absolute left-[19px] top-1 bottom-1 w-px bg-gradient-to-b from-indigo-500/30 via-amber-500/30 via-red-500/30 via-emerald-500/30 to-violet-500/30" />

              <div className="space-y-5">
                {([
                  { text: t('step1'), border: 'border-indigo-500/20', bg: 'bg-indigo-500/10', textColor: 'text-indigo-600' },
                  { text: t('step2'), border: 'border-amber-500/20', bg: 'bg-amber-500/10', textColor: 'text-amber-600' },
                  { text: t('step3'), border: 'border-red-500/20', bg: 'bg-red-500/10', textColor: 'text-red-600' },
                  { text: t('step4'), border: 'border-emerald-500/20', bg: 'bg-emerald-500/10', textColor: 'text-emerald-600' },
                  { text: t('step5'), border: 'border-violet-500/20', bg: 'bg-violet-500/10', textColor: 'text-violet-600' },
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
                    <div className={`ml-3 p-4 rounded-xl border transition-all duration-200 group-hover:border-primary/20 group-hover:bg-muted/50 ${step.border} bg-card`}>
                      <p className="text-sm text-foreground/80 leading-relaxed">{step.text}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            <div className="mt-8 p-4 rounded-xl bg-gradient-to-r from-indigo-500/5 to-violet-500/5 border border-border">
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t('outro')}
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
