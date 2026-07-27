'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, CheckCircle2, XCircle, Globe, Search, ShieldCheck, Sparkles, Wallet, Brain } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import type { SSEStreamEvent } from '@/lib/types';

interface StepInfo {
  id: string;
  label: string;
  icon: React.ReactNode;
  detail: string;
  status: 'pending' | 'active' | 'done' | 'error';
}

interface LogEntry {
  id: number;
  message: string;
  timestamp: string;
  type: 'info' | 'error' | 'success';
}

interface StreamingProgressProps {
  destination: string;
  onCancel: () => void;
  onComplete: () => void;
  event: SSEStreamEvent | null;
}

const STEP_MAP: Record<string, { label: string; icon: React.ReactNode }> = {
  TravelAgent: { label: 'Analyzing your request', icon: <Brain className="w-4 h-4" /> },
  researcher: { label: 'Researching destination', icon: <Search className="w-4 h-4" /> },
  validator: { label: 'Validating itinerary', icon: <ShieldCheck className="w-4 h-4" /> },
  enricher: { label: 'Enriching with local tips', icon: <Sparkles className="w-4 h-4" /> },
  cost_optimizer: { label: 'Optimizing budget', icon: <Wallet className="w-4 h-4" /> },
};

const STEP_ORDER = ['TravelAgent', 'researcher', 'validator', 'enricher', 'cost_optimizer'];
const TOTAL_STEPS = STEP_ORDER.length;

function formatTime(d: Date): string {
  return d.toLocaleTimeString('en-US', { minute: '2-digit', second: '2-digit' });
}

export default function StreamingProgress({ destination, onCancel, onComplete, event }: StreamingProgressProps) {
  const [steps, setSteps] = useState<StepInfo[]>(() =>
    STEP_ORDER.map((id) => ({
      id,
      label: STEP_MAP[id]?.label ?? id,
      icon: STEP_MAP[id]?.icon ?? <Loader2 className="w-4 h-4" />,
      detail: '',
      status: 'pending' as const,
    }))
  );
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentTool, setCurrentTool] = useState('');
  const logEndRef = useRef<HTMLDivElement>(null);
  const logIdRef = useRef(0);

  const addLog = useCallback((message: string, type: LogEntry['type'] = 'info') => {
    logIdRef.current += 1;
    setLogs(prev => [...prev.slice(-99), {
      id: logIdRef.current,
      message,
      timestamp: formatTime(new Date()),
      type,
    }]);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    if (!event) return;
    const ev = event.event;

    if (ev === 'on_chain_start' && event.name === 'TravelAgent') {
      addLog('AI travel agent started working...');
      setSteps(prev => prev.map(s => s.id === 'TravelAgent' ? { ...s, status: 'active' } : s));
    }

    if (ev === 'on_chain_end' && event.name === 'TravelAgent') {
      addLog('AI travel agent completed analysis', 'success');
      setSteps(prev => prev.map(s => s.id === 'TravelAgent' ? { ...s, status: 'done' } : s));
      setProgress(prev => Math.max(prev, 20));
    }

    if (ev === 'on_tool_start') {
      const name = event.name ?? '';
      setCurrentTool(name);
      addLog(`→ ${name} starting...`);

      if (STEP_MAP[name]) {
        setSteps(prev => prev.map(s => s.id === name ? { ...s, status: 'active', detail: '' } : s));
      } else {
        setSteps(prev => {
          const exists = prev.some(s => s.id === name);
          if (exists) return prev.map(s => s.id === name ? { ...s, status: 'active' } : s);
          addLog(`Unknown tool: ${name}`);
          return prev;
        });
      }
    }

    if (ev === 'on_tool_end') {
      const name = event.name ?? '';
      addLog(`✓ ${name} complete`, 'success');
      setCurrentTool('');

      if (STEP_MAP[name]) {
        const idx = STEP_ORDER.indexOf(name);
        const newProgress = Math.round(((idx + 1) / TOTAL_STEPS) * 100);
        setProgress(Math.min(newProgress, 95));
        setSteps(prev => prev.map(s => s.id === name ? { ...s, status: 'done' } : s));
      }
    }

    if (ev === 'final') {
      addLog('Itinerary ready!', 'success');
      setProgress(100);
      setSteps(prev => prev.map(s => s.status === 'pending' ? { ...s, status: 'done' } : s));
      setTimeout(onComplete, 600);
    }

    if (ev === 'error') {
      const errMsg = String(event.data ?? 'Unknown error');
      addLog(`Error: ${errMsg}`, 'error');
      setSteps(prev => prev.map(s => s.status === 'active' ? { ...s, status: 'error' } : s));
    }
  }, [event, addLog, onComplete]);

  const activeIdx = steps.findIndex(s => s.status === 'active');

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl overflow-hidden">
          <div className="h-0.5 bg-gradient-to-r from-sky-500/10 via-sky-400/30 to-sky-500/10" />

          {/* Header */}
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-5">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 3, ease: 'linear' }}
              >
                <Globe className="w-6 h-6 text-sky-400" />
              </motion.div>
              <div>
                <h3 className="text-sm font-semibold text-white">Generating your itinerary</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  AI is planning your trip to{' '}
                  <span className="text-sky-300 font-medium">{destination}</span>
                </p>
              </div>
            </div>

            {/* Progress bar */}
            <div className="mb-5">
              <Progress value={progress} className="h-1.5 bg-white/[0.05]" />
              <p className="text-xs text-muted-foreground/60 mt-1.5 text-right">{progress}%</p>
            </div>

            {/* Steps */}
            <div className="space-y-2 mb-5">
              {steps.map((step, i) => (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={`flex items-center gap-3 p-2.5 rounded-lg transition-colors ${
                    step.status === 'active'
                      ? 'bg-sky-500/8 border border-sky-500/15'
                      : step.status === 'done'
                        ? 'bg-emerald-500/5'
                        : step.status === 'error'
                          ? 'bg-red-500/8'
                          : 'opacity-40'
                  }`}
                >
                  <div className="shrink-0 w-5 h-5 flex items-center justify-center">
                    {step.status === 'done' ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : step.status === 'active' ? (
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
                      >
                        <Loader2 className="w-4 h-4 text-sky-400" />
                      </motion.div>
                    ) : step.status === 'error' ? (
                      <XCircle className="w-5 h-5 text-red-400" />
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-white/20" />
                    )}
                  </div>
                  <span
                    className={`text-xs font-medium ${
                      step.status === 'active'
                        ? 'text-sky-200'
                        : step.status === 'done'
                          ? 'text-emerald-200'
                          : step.status === 'error'
                            ? 'text-red-200'
                            : 'text-muted-foreground'
                    }`}
                  >
                    {step.icon}
                  </span>
                  <span
                    className={`text-xs ${
                      step.status === 'active'
                        ? 'text-white'
                        : step.status === 'done'
                          ? 'text-emerald-100'
                          : step.status === 'error'
                            ? 'text-red-200'
                            : 'text-muted-foreground'
                    }`}
                  >
                    {step.label}
                  </span>
                  {step.status === 'active' && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: [0, 1, 0] }}
                      transition={{ repeat: Infinity, duration: 1.5 }}
                      className="text-[10px] text-sky-400/60 ml-auto"
                    >
                      working…
                    </motion.span>
                  )}
                </motion.div>
              ))}
            </div>

            {/* Live activity log */}
            <div className="rounded-lg bg-black/20 border border-white/[0.05] p-3 max-h-36 overflow-y-auto">
              <p className="text-[10px] text-muted-foreground/40 uppercase tracking-wider mb-2 font-medium">
                Activity Log
              </p>
              <AnimatePresence initial={false}>
                {logs.map((log) => (
                  <motion.div
                    key={log.id}
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex items-start gap-2 py-0.5"
                  >
                    <span className="text-[10px] text-muted-foreground/40 shrink-0 w-14 font-mono">
                      {log.timestamp}
                    </span>
                    <span
                      className={`text-[11px] leading-tight ${
                        log.type === 'error'
                          ? 'text-red-300'
                          : log.type === 'success'
                            ? 'text-emerald-300'
                            : 'text-muted-foreground'
                      }`}
                    >
                      {log.message}
                    </span>
                  </motion.div>
                ))}
              </AnimatePresence>
              <div ref={logEndRef} />
            </div>

            {/* Cancel button */}
            <div className="mt-4 text-center">
              <button
                onClick={onCancel}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-red-400 hover:text-red-300 transition-colors cursor-pointer"
              >
                <XCircle className="w-3.5 h-3.5" />
                Cancel request
              </button>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
