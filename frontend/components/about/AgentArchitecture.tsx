'use client';

import { motion } from 'framer-motion';
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
}

const agents: AgentDef[] = [
  { nameKey: 'agentResearcherName', descKey: 'agentResearcherDesc', icon: Search, hasInternet: true },
  { nameKey: 'agentConstraintAnalyzerName', descKey: 'agentConstraintAnalyzerDesc', icon: Scale, hasInternet: false },
  { nameKey: 'agentRiskDetectorName', descKey: 'agentRiskDetectorDesc', icon: ShieldAlert, hasInternet: true },
  { nameKey: 'agentMultiPlanGeneratorName', descKey: 'agentMultiPlanGeneratorDesc', icon: Layers, hasInternet: false },
  { nameKey: 'agentValidatorName', descKey: 'agentValidatorDesc', icon: CheckCircle2, hasInternet: false },
  { nameKey: 'agentQualityScorerName', descKey: 'agentQualityScorerDesc', icon: Star, hasInternet: false },
  { nameKey: 'agentCostOptimizerName', descKey: 'agentCostOptimizerDesc', icon: TrendingDown, hasInternet: true },
  { nameKey: 'agentEnricherName', descKey: 'agentEnricherDesc', icon: Sparkles, hasInternet: true },
];

export default function AgentArchitecture() {
  const t = useTranslations('about');

  return (
    <section className="relative mb-20">
      <motion.div
        initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
        whileInView={{ opacity: 1, y: 0, filter: 'blur(0)' }}
        viewport={{ once: true }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="mb-10"
      >
        <p className="font-mono text-[10px] tracking-[0.25em] text-primary mb-2">SECTION 01 · PERSONNEL</p>
        <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-2 tracking-tight">
          {t('agentsTitle')}
        </h2>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          {t('agentsSubtitle')}
        </p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {agents.map((agent, i) => (
          <motion.div
            key={agent.nameKey}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: (i % 4) * 0.08, ease: [0.22, 1, 0.36, 1] }}
            className="relative overflow-hidden rounded-lg border border-border bg-card p-6 transition-shadow hover:shadow-md"
          >
            <div className="absolute top-0 left-0 right-0 h-[3px] bg-primary/60" />
            <span
              className={`absolute top-3.5 right-3.5 border border-primary px-2 py-0.5 font-mono text-[9px] font-bold tracking-[0.1em] text-primary opacity-70 ${
                agent.hasInternet ? '' : 'border-accent-foreground text-accent-foreground'
              }`}
              style={{ transform: 'rotate(3deg)' }}
            >
              {agent.hasInternet ? 'ACTIVE' : 'ANALYSIS'}
            </span>
            <p className="font-mono text-[11px] tracking-[0.05em] text-primary mb-2">
              FILE {String(i + 1).padStart(2, '0')}
            </p>
            <div className="mb-2">
              <agent.icon className="w-5 h-5 text-primary" />
            </div>
            <h3 className="text-base font-semibold text-foreground mb-1.5">
              {t(agent.nameKey)}
            </h3>
            <p className="text-xs text-muted-foreground leading-relaxed mb-3">
              {t(agent.descKey)}
            </p>
            {agent.hasInternet && (
              <span className="inline-flex items-center gap-1 font-mono text-[10px] text-primary border border-primary/50 px-2 py-0.5 rounded-sm opacity-80">
                <Search className="w-2.5 h-2.5" />
                {t('agentWithTools')}
              </span>
            )}
          </motion.div>
        ))}
      </div>
    </section>
  );
}
