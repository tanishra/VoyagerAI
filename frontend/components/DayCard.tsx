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
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import type { DayPlan, TimeSlot } from '@/lib/types';

interface DayCardProps {
  day: DayPlan;
  index: number;
  onReplan: (dayNumber: number, reason: string) => void;
  replanLoading: boolean;
}

const timeSlots = [
  {
    key: 'morning' as const,
    label: 'Morning',
    emoji: '🌅',
    icon: Sunrise,
    gradient: 'from-amber-500/15 to-orange-500/15',
    textColor: 'text-amber-400',
    borderColor: 'border-amber-500/20',
  },
  {
    key: 'afternoon' as const,
    label: 'Afternoon',
    emoji: '☀️',
    icon: Sun,
    gradient: 'from-blue-500/15 to-cyan-500/15',
    textColor: 'text-blue-400',
    borderColor: 'border-blue-500/20',
  },
  {
    key: 'evening' as const,
    label: 'Evening',
    emoji: '🌙',
    icon: Moon,
    gradient: 'from-purple-500/15 to-indigo-500/15',
    textColor: 'text-purple-400',
    borderColor: 'border-purple-500/20',
  },
];

function TimeSlotCard({
  slot,
  data,
  config,
}: {
  slot: typeof timeSlots[number];
  data: TimeSlot;
  config: typeof timeSlots[number];
}) {
  return (
    <div className={`p-4 rounded-xl bg-gradient-to-br ${config.gradient} border ${config.borderColor}`}>
      <div className="flex items-center gap-2 mb-2.5">
        <span className="text-base">{config.emoji}</span>
        <span className={`text-sm font-semibold ${config.textColor}`}>{config.label}</span>
      </div>
      <p className="text-sm font-medium text-white/90 mb-2">{data.activity}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <MapPin className="w-3 h-3" />
          {data.location}
        </span>
        <span className="flex items-center gap-1">
          <DollarSign className="w-3 h-3" />
          ${data.cost_usd}
        </span>
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {data.duration}
        </span>
      </div>
    </div>
  );
}

export default function DayCard({ day, index, onReplan, replanLoading }: DayCardProps) {
  const [showReplan, setShowReplan] = useState(false);
  const [reason, setReason] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (showReplan && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [showReplan]);

  const handleReplan = () => {
    if (reason.trim()) {
      onReplan(day.day, reason);
      setReason('');
      setShowReplan(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setShowReplan(false);
      setReason('');
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.6,
        delay: index * 0.1,
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      <Card
        className="relative overflow-hidden border-white/10 bg-white/[0.03] backdrop-blur-2xl shadow-lg hover:shadow-xl hover:border-white/15 transition-all duration-500 group"
        id={`day-card-${day.day}`}
      >
        {/* Top gradient */}
        <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-purple-500/60 via-blue-500/60 to-cyan-500/60 opacity-50 group-hover:opacity-100 transition-opacity" />

        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <Badge variant="secondary" className="bg-white/[0.06] border border-white/10 text-white/50 text-xs mb-2">
                Day {day.day}
              </Badge>
              <h3 className="text-lg font-bold text-white">{day.theme}</h3>
            </div>
            <Badge
              variant="outline"
              className="bg-emerald-500/10 border-emerald-500/30 text-emerald-400 text-sm font-semibold tabular-nums"
            >
              <DollarSign className="w-3.5 h-3.5 mr-0.5" />
              {day.daily_cost_usd}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="space-y-3 pb-5">
          {/* Time slots */}
          {timeSlots.map((slot) => (
            <TimeSlotCard
              key={slot.key}
              slot={slot}
              data={day[slot.key]}
              config={slot}
            />
          ))}

          {/* Transport & Accommodation */}
          <div className="flex flex-col sm:flex-row gap-3 pt-2 border-t border-white/5">
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

          {/* Replan section */}
          <div className="pt-3 border-t border-white/5">
            <Button
              variant="ghost"
              size="sm"
              id={`replan-toggle-${day.day}`}
              onClick={() => setShowReplan(!showReplan)}
              className="text-xs text-muted-foreground hover:text-white/80 transition-colors cursor-pointer p-0 h-auto"
              aria-expanded={showReplan}
              aria-controls={`replan-form-${day.day}`}
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Replan This Day
              <ChevronDown className={`w-3 h-3 ml-1 transition-transform ${showReplan ? 'rotate-180' : ''}`} />
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
                      id={`replan-reason-${day.day}`}
                      placeholder="What would you like changed? e.g., More outdoor activities..."
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      onKeyDown={handleKeyDown}
                      className="bg-white/[0.05] border-white/10 min-h-[70px] text-sm resize-none placeholder:text-white/20"
                      aria-label={`Reason to replan day ${day.day}`}
                    />
                    <Button
                      size="sm"
                      id={`replan-submit-${day.day}`}
                      disabled={!reason.trim() || replanLoading}
                      onClick={handleReplan}
                      className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 border-0 text-xs cursor-pointer disabled:opacity-40"
                    >
                      {replanLoading ? (
                        <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                        </motion.div>
                      ) : (
                        <Send className="w-3.5 h-3.5 mr-1.5" />
                      )}
                      {replanLoading ? 'Replanning…' : 'Replan'}
                    </Button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
