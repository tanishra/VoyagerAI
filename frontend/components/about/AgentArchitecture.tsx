'use client';

import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import {
  Search,
  Scale,
  ShieldAlert,
  Layers,
  CheckCircle2,
  Star,
  TrendingDown,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';
import { useTranslations } from 'next-intl';

interface AgentDef {
  nameKey: string;
  descKey: string;
  icon: LucideIcon;
  hasInternet: boolean;
  gradient: string;
  border: string;
  color: string;
  glow: string;
}

const agents: AgentDef[] = [
  {
    nameKey: 'agentResearcherName',
    descKey: 'agentResearcherDesc',
    icon: Search,
    hasInternet: true,
    gradient: 'from-blue-500/10 to-cyan-500/10',
    border: 'border-blue-500/20',
    color: 'text-blue-600',
    glow: 'shadow-blue-500/10',
  },
  {
    nameKey: 'agentConstraintAnalyzerName',
    descKey: 'agentConstraintAnalyzerDesc',
    icon: Scale,
    hasInternet: false,
    gradient: 'from-indigo-500/10 to-violet-500/10',
    border: 'border-indigo-500/20',
    color: 'text-indigo-600',
    glow: 'shadow-indigo-500/10',
  },
  {
    nameKey: 'agentRiskDetectorName',
    descKey: 'agentRiskDetectorDesc',
    icon: ShieldAlert,
    hasInternet: true,
    gradient: 'from-red-500/10 to-orange-500/10',
    border: 'border-red-500/20',
    color: 'text-red-600',
    glow: 'shadow-red-500/10',
  },
  {
    nameKey: 'agentMultiPlanGeneratorName',
    descKey: 'agentMultiPlanGeneratorDesc',
    icon: Layers,
    hasInternet: false,
    gradient: 'from-violet-500/10 to-purple-500/10',
    border: 'border-violet-500/20',
    color: 'text-violet-600',
    glow: 'shadow-violet-500/10',
  },
  {
    nameKey: 'agentValidatorName',
    descKey: 'agentValidatorDesc',
    icon: CheckCircle2,
    hasInternet: false,
    gradient: 'from-emerald-500/10 to-green-500/10',
    border: 'border-emerald-500/20',
    color: 'text-emerald-600',
    glow: 'shadow-emerald-500/10',
  },
  {
    nameKey: 'agentQualityScorerName',
    descKey: 'agentQualityScorerDesc',
    icon: Star,
    hasInternet: false,
    gradient: 'from-amber-500/10 to-yellow-500/10',
    border: 'border-amber-500/20',
    color: 'text-amber-600',
    glow: 'shadow-amber-500/10',
  },
  {
    nameKey: 'agentCostOptimizerName',
    descKey: 'agentCostOptimizerDesc',
    icon: TrendingDown,
    hasInternet: true,
    gradient: 'from-teal-500/10 to-cyan-500/10',
    border: 'border-teal-500/20',
    color: 'text-teal-600',
    glow: 'shadow-teal-500/10',
  },
  {
    nameKey: 'agentEnricherName',
    descKey: 'agentEnricherDesc',
    icon: Sparkles,
    hasInternet: true,
    gradient: 'from-pink-500/10 to-rose-500/10',
    border: 'border-pink-500/20',
    color: 'text-pink-600',
    glow: 'shadow-pink-500/10',
  },
];

export default function AgentArchitecture() {
  const t = useTranslations('about');
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start end', 'end start'],
  });

  const yUp = useTransform(scrollYProgress, [0, 0.5, 1], [20, 0, -20]);
  const yDown = useTransform(scrollYProgress, [0, 0.5, 1], [-20, 0, 20]);

  return (
    <section ref={containerRef} className="relative mb-20">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="text-center mb-10"
      >
        <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-3 tracking-tight">
          {t('agentsTitle')}
        </h2>
        <p className="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          {t('agentsSubtitle')}
        </p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {agents.map((agent, i) => {
          const parallaxY = i % 2 === 0 ? yUp : yDown;
          return (
            <motion.div
              key={agent.nameKey}
              style={{ y: parallaxY }}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: (i % 4) * 0.08 }}
              whileHover={{ scale: 1.03 }}
              className={`p-5 rounded-2xl bg-gradient-to-br ${agent.gradient} border ${agent.border} bg-card/80 backdrop-blur-sm transition-shadow hover:shadow-lg ${agent.glow}`}
            >
              <div className={`p-2.5 w-fit rounded-xl bg-card border ${agent.border} mb-3 shadow-sm`}>
                <agent.icon className={`w-5 h-5 ${agent.color}`} />
              </div>
              <h3 className="text-base font-semibold text-foreground mb-1.5">
                {t(agent.nameKey)}
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed mb-3">
                {t(agent.descKey)}
              </p>
              {agent.hasInternet && (
                <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/15">
                  <Search className="w-2.5 h-2.5" />
                  {t('agentWithTools')}
                </span>
              )}
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
