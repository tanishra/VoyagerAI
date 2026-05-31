'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sunrise,
  Sun,
  Moon,
  MapPin,
  DollarSign,
  Clock,
  Car,
  Hotel,
  Lightbulb,
  RefreshCw,
  Send,
  ChevronDown,
  Timer,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import type { DayPlan, TimeSlot } from '@/lib/types';

interface TimelineDayProps {
  day: DayPlan;
  index: number;
  onReplan: (dayNumber: number, reason: string) => void;
  replanLoading: boolean;
  isLast: boolean;
}

const timeSlotConfig = [
  { key: 'morning' as const, label: 'Morning', icon: Sunrise, gradient: 'from-amber-500/15 to-orange-500/15', textColor: 'text-amber-400', borderColor: 'border-amber-500/20' },
  { key: 'afternoon' as const, label: 'Afternoon', icon: Sun, gradient: 'from-blue-500/15 to-cyan-500/15', textColor: 'text-blue-400', borderColor: 'border-blue-500/20' },
  { key: 'evening' as const, label: 'Evening', icon: Moon, gradient: 'from-purple-500/15 to-indigo-500/15', textColor: 'text-purple-400', borderColor: 'border-purple-500/20' },
];

const themeAccents: Record<string, string> = {
  adventure: 'border-emerald-500/30',
  cultural: 'border-violet-500/30',
  luxury: 'border-amber-500/30',
  budget: 'border-blue-500/30',
};

function TimeSlotBadge({ data, config }: { data: TimeSlot; config: typeof timeSlotConfig[number] }) {
  return (
    <div className={`p-3 rounded-xl bg-gradient-to-br ${config.gradient} border ${config.borderColor}`}>
      <div className="flex items-center gap-2 mb-1.5">
        <config.icon className={`w-3.5 h-3.5 ${config.textColor}`} />
        <span className={`text-xs font-semibold ${config.textColor}`}>{config.label}</span>
      </div>
      <p className="text-sm font-medium text-white/90 mb-1.5 leading-snug">{data.activity}</p>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{data.location}</span>
        <span className="flex items-center gap-1"><DollarSign className="w-3 h-3" />{data.cost_usd}</span>
        <span className="flex items-center gap-1"><Timer className="w-3 h-3" />{data.duration}</span>
      </div>
    </div>
  );
}

export default function TimelineDay({ day, index, onReplan, replanLoading, isLast }: TimelineDayProps) {
  const [expanded, setExpanded] = useState(true);
  const [showReplan, setShowReplan] = useState(false);
  const [reason, setReason] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (showReplan && textareaRef.current) textareaRef.current.focus();
  }, [showReplan]);

  const handleReplan = () => {
    if (reason.trim()) {
      onReplan(day.day, reason);
      setReason('');
      setShowReplan(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setShowReplan(false); setReason(''); }
  };

  return (
    <div className="flex gap-4 group">
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: index * 0.1, type: 'spring', stiffness: 200 }}
          className="w-10 h-10 rounded-full bg-gradient-to-br from-sky-500 to-blue-600 flex items-center justify-center text-sm font-bold text-white shadow-lg shadow-sky-500/20 shrink-0 z-10"
        >
          {day.day}
        </motion.div>
        {!isLast && <div className="w-px flex-1 bg-gradient-to-b from-sky-500/40 to-transparent min-h-[24px]" />}
      </div>

      {/* Day card */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: index * 0.1, ease: [0.22, 1, 0.36, 1] }}
        className="flex-1 pb-6"
      >
        <Card className="relative overflow-hidden border-white/10 bg-white/[0.03] backdrop-blur-2xl shadow-lg hover:shadow-xl hover:border-white/15 transition-all duration-500">
          <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-sky-500/60 via-blue-500/60 to-indigo-500/60 opacity-50 group-hover:opacity-100 transition-opacity" />

          <CardContent className="p-5">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">Day {day.day}</span>
                <span className="text-muted-foreground/30">·</span>
                <h3 className="text-base font-bold text-white">{day.theme}</h3>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-emerald-500/10 border-emerald-500/30 text-emerald-400 text-xs font-semibold tabular-nums">
                  <DollarSign className="w-3 h-3 mr-0.5" />
                  {day.daily_cost_usd}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setExpanded(!expanded)}
                  className="p-1 h-auto text-muted-foreground hover:text-white cursor-pointer"
                  aria-label={expanded ? 'Collapse day' : 'Expand day'}
                >
                  <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
                </Button>
              </div>
            </div>

            <AnimatePresence>
              {expanded && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="overflow-hidden"
                >
                  <div className="space-y-3 pt-1">
                    {/* Time slots */}
                    <div className="grid sm:grid-cols-3 gap-2">
                      {timeSlotConfig.map(slot => (
                        <TimeSlotBadge key={slot.key} data={day[slot.key]} config={slot} />
                      ))}
                    </div>

                    {/* Transport & Accommodation */}
                    <div className="flex flex-col sm:flex-row gap-2 pt-2 border-t border-white/5">
                      <div className="flex items-center gap-2 text-sm text-white/60 flex-1">
                        <Car className="w-4 h-4 text-blue-400 shrink-0" />
                        <span>{day.transport}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-white/60 flex-1">
                        <Hotel className="w-4 h-4 text-purple-400 shrink-0" />
                        <span>{day.accommodation}</span>
                      </div>
                    </div>

                    {/* Tips */}
                    {day.tips.length > 0 && (
                      <div className="pt-2 border-t border-white/5">
                        <div className="flex items-center gap-1.5 mb-2">
                          <Lightbulb className="w-3.5 h-3.5 text-yellow-400" />
                          <span className="text-xs font-medium text-yellow-400/80">Tips</span>
                        </div>
                        <ul className="space-y-1">
                          {day.tips.map((tip, i) => (
                            <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                              <span className="text-white/20 mt-px">▸</span>
                              <span>{tip}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Replan */}
                    <div className="pt-2 border-t border-white/5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowReplan(!showReplan)}
                        className="text-xs text-muted-foreground hover:text-white/80 transition-colors cursor-pointer p-0 h-auto"
                        aria-expanded={showReplan}
                        aria-controls={`replan-form-${day.day}`}
                      >
                        <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                        Replan This Day
                      </Button>

                      <AnimatePresence>
                        {showReplan && (
                          <motion.div
                            id={`replan-form-${day.day}`}
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.3 }}
                            className="overflow-hidden"
                          >
                            <div className="pt-3 space-y-2.5">
                              <Textarea
                                ref={textareaRef}
                                placeholder="What would you like changed?"
                                value={reason}
                                onChange={e => setReason(e.target.value)}
                                onKeyDown={handleKeyDown}
                                className="bg-white/5 border-white/10 min-h-[70px] text-sm resize-none placeholder:text-white/20"
                                aria-label={`Reason to replan day ${day.day}`}
                              />
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  disabled={!reason.trim() || replanLoading}
                                  onClick={handleReplan}
                                  className="bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 border-0 text-xs cursor-pointer disabled:opacity-40"
                                >
                                  {replanLoading ? (
                                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                                      <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                                    </motion.div>
                                  ) : <Send className="w-3.5 h-3.5 mr-1.5" />}
                                  {replanLoading ? 'Replanning…' : 'Replan'}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => { setShowReplan(false); setReason(''); }}
                                  className="text-xs text-muted-foreground hover:text-white cursor-pointer"
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
