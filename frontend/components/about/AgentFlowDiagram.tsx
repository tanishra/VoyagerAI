'use client';

import { useRef } from 'react';
import { motion, useScroll, useTransform, useSpring } from 'framer-motion';
import {
  Cpu,
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

interface FlowAgent {
  nameKey: string;
  icon: LucideIcon;
  color: string;
  border: string;
  bg: string;
  isParallel: boolean;
}

const flowAgents: FlowAgent[] = [
  { nameKey: 'agentResearcherName', icon: Search, color: 'text-blue-600', border: 'border-blue-500/30', bg: 'bg-blue-500/10', isParallel: true },
  { nameKey: 'agentConstraintAnalyzerName', icon: Scale, color: 'text-indigo-600', border: 'border-indigo-500/30', bg: 'bg-indigo-500/10', isParallel: true },
  { nameKey: 'agentRiskDetectorName', icon: ShieldAlert, color: 'text-red-600', border: 'border-red-500/30', bg: 'bg-red-500/10', isParallel: true },
  { nameKey: 'agentMultiPlanGeneratorName', icon: Layers, color: 'text-violet-600', border: 'border-violet-500/30', bg: 'bg-violet-500/10', isParallel: false },
  { nameKey: 'agentValidatorName', icon: CheckCircle2, color: 'text-emerald-600', border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', isParallel: false },
  { nameKey: 'agentQualityScorerName', icon: Star, color: 'text-amber-600', border: 'border-amber-500/30', bg: 'bg-amber-500/10', isParallel: false },
  { nameKey: 'agentCostOptimizerName', icon: TrendingDown, color: 'text-teal-600', border: 'border-teal-500/30', bg: 'bg-teal-500/10', isParallel: false },
  { nameKey: 'agentEnricherName', icon: Sparkles, color: 'text-pink-600', border: 'border-pink-500/30', bg: 'bg-pink-500/10', isParallel: false },
];

export default function AgentFlowDiagram() {
  const t = useTranslations('about');
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start 80%', 'end 20%'],
  });

  const lineProgress = useSpring(scrollYProgress, {
    stiffness: 80,
    damping: 25,
    mass: 0.3,
  });

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
          {t('flowTitle')}
        </h2>
        <p className="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          {t('flowSubtitle')}
        </p>
      </motion.div>

      <div className="relative max-w-4xl mx-auto">
        {/* SVG connecting lines overlay */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none hidden md:block"
          viewBox="0 0 800 600"
          preserveAspectRatio="none"
        >
          {flowAgents.map((_, i) => {
            const angle = (i / flowAgents.length) * Math.PI - Math.PI / 2;
            const x2 = 400 + Math.cos(angle) * 280;
            const y2 = 180 + Math.sin(angle) * 180 + 60;
            return (
              <motion.line
                key={i}
                x1={400}
                y1={80}
                x2={x2}
                y2={y2}
                stroke="url(#flowGradient)"
                strokeWidth={flowAgents[i].isParallel ? 2 : 1.5}
                strokeDasharray="4 4"
                style={{
                  pathLength: lineProgress,
                  opacity: useTransform(lineProgress, [0, 0.1, 0.9, 1], [0, 1, 1, 0.6]),
                }}
              />
            );
          })}
          <defs>
            <linearGradient id="flowGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.3" />
            </linearGradient>
          </defs>
        </svg>

        {/* Orchestrator node */}
        <div className="relative flex justify-center mb-12 md:mb-20">
          <motion.div
            initial={{ opacity: 0, scale: 0.5 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="relative"
          >
            <motion.div
              animate={{
                boxShadow: [
                  '0 0 20px 4px rgba(99, 102, 241, 0.15)',
                  '0 0 40px 8px rgba(99, 102, 241, 0.25)',
                  '0 0 20px 4px rgba(99, 102, 241, 0.15)',
                ],
              }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              className="w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 relative z-10"
            >
              <Cpu className="w-8 h-8 text-white" />
            </motion.div>
            <div className="mt-3 text-center">
              <p className="text-sm font-semibold text-foreground">
                {t('flowOrchestrator')}
              </p>
            </div>
          </motion.div>
        </div>

        {/* Parallel batch indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="relative md:absolute md:left-1/2 md:-translate-x-1/2 md:top-32 mb-6 md:mb-0"
        >
          <span className="inline-flex items-center gap-1.5 text-[10px] font-medium px-3 py-1 rounded-full bg-amber-500/10 text-amber-600 border border-amber-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            {t('flowParallelBatch')}
          </span>
        </motion.div>

        {/* Subagent nodes grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-3 relative z-10 mt-8 md:mt-32">
          {flowAgents.map((agent, i) => (
            <motion.div
              key={agent.nameKey}
              initial={{ opacity: 0, scale: 0.3 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{
                duration: 0.4,
                delay: 0.1 + i * 0.06,
                type: 'spring',
                stiffness: 200,
                damping: 15,
              }}
              whileHover={{ scale: 1.08, zIndex: 20 }}
              className={`relative p-3 rounded-xl border ${agent.border} ${agent.bg} backdrop-blur-sm flex flex-col items-center text-center gap-2 transition-shadow hover:shadow-md`}
            >
              {agent.isParallel && (
                <span className="absolute -top-1.5 -right-1.5 w-2 h-2 rounded-full bg-amber-500 ring-2 ring-card" />
              )}
              <div className={`p-1.5 rounded-lg bg-card border ${agent.border}`}>
                <agent.icon className={`w-4 h-4 ${agent.color}`} />
              </div>
              <span className="text-[11px] font-medium text-foreground/80 leading-tight">
                {t(agent.nameKey)}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
