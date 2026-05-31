'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Luggage, ChevronDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';

interface WarningsSectionProps {
  warnings: string[];
  packingEssentials: string[];
}

export default function WarningsSection({ warnings, packingEssentials }: WarningsSectionProps) {
  const [showWarnings, setShowWarnings] = useState(true);
  const [showPacking, setShowPacking] = useState(true);

  if (warnings.length === 0 && packingEssentials.length === 0) return null;

  return (
    <div className="space-y-4">
      {/* Warnings */}
      {warnings.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <Card className="border-amber-500/20 bg-amber-500/[0.04] backdrop-blur-xl overflow-hidden">
            <div className="h-0.5 bg-gradient-to-r from-amber-500/60 via-yellow-500/60 to-amber-500/60" />
            <CardContent className="p-5">
              <button
                onClick={() => setShowWarnings(!showWarnings)}
                className="flex items-center gap-2 mb-3 w-full text-left cursor-pointer"
                aria-expanded={showWarnings}
              >
                <div className="p-1.5 rounded-lg bg-amber-500/10">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                </div>
                <h3 className="text-sm font-semibold text-amber-300 flex-1">
                  Travel Warnings <span className="text-xs text-amber-400/60 font-normal">({warnings.length})</span>
                </h3>
                <ChevronDown className={`w-4 h-4 text-amber-400/60 transition-transform ${showWarnings ? 'rotate-180' : ''}`} />
              </button>

              <AnimatePresence>
                {showWarnings && (
                  <motion.ul
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-2 overflow-hidden"
                  >
                    {warnings.map((warning, i) => (
                      <motion.li
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="flex items-start gap-2 text-sm text-amber-200/80"
                      >
                        <span className="text-amber-400 mt-1 shrink-0">•</span>
                        <span>{warning}</span>
                      </motion.li>
                    ))}
                  </motion.ul>
                )}
              </AnimatePresence>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Packing Essentials */}
      {packingEssentials.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl overflow-hidden">
            <div className="h-0.5 bg-gradient-to-r from-cyan-500/40 via-blue-500/40 to-purple-500/40" />
            <CardContent className="p-5">
              <button
                onClick={() => setShowPacking(!showPacking)}
                className="flex items-center gap-2 mb-3 w-full text-left cursor-pointer"
                aria-expanded={showPacking}
              >
                <div className="p-1.5 rounded-lg bg-cyan-500/10">
                  <Luggage className="w-4 h-4 text-cyan-400" />
                </div>
                <h3 className="text-sm font-semibold text-white/90 flex-1">
                  Packing Essentials <span className="text-xs text-white/40 font-normal">({packingEssentials.length})</span>
                </h3>
                <ChevronDown className={`w-4 h-4 text-white/40 transition-transform ${showPacking ? 'rotate-180' : ''}`} />
              </button>

              <AnimatePresence>
                {showPacking && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.3 }}
                    className="flex flex-wrap gap-2 overflow-hidden"
                  >
                    {packingEssentials.map((item, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.03 }}
                      >
                        <Badge
                          variant="secondary"
                          className="bg-white/[0.06] border border-white/10 text-white/70 hover:bg-white/10 hover:scale-105 transition-all duration-200"
                        >
                          {item}
                        </Badge>
                      </motion.div>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
