'use client';

import { motion } from 'framer-motion';
import { MapPin, Calendar, Plane } from 'lucide-react';

interface DestinationHeroProps {
  destination: string;
  totalDays: number;
}

export default function DestinationHero({ destination, totalDays }: DestinationHeroProps) {
  const gradient = 'from-sky-600/30 via-blue-600/20 to-indigo-600/30';

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-2xl shadow-xl"
    >
      {/* Animated gradient background */}
      <div className={`absolute inset-0 bg-gradient-to-br ${gradient}`} />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(14,165,233,0.15),transparent_50%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,rgba(99,102,241,0.1),transparent_50%)]" />

      {/* Subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative p-6 md:p-8">
        <div className="flex items-center gap-4">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
            className="p-3 rounded-2xl bg-gradient-to-br from-sky-500/20 to-blue-500/20 border border-sky-500/20 shadow-lg shadow-sky-500/5"
          >
            <Plane className="w-7 h-7 text-sky-400" />
          </motion.div>

          <div className="flex-1">
            <motion.h1
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15 }}
              className="text-2xl md:text-3xl font-bold text-white"
            >
              {destination}
            </motion.h1>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.25 }}
              className="flex items-center gap-4 mt-1.5"
            >
              <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Calendar className="w-4 h-4 text-sky-400" />
                {totalDays} {totalDays === 1 ? 'day' : 'days'}
              </span>
              <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <MapPin className="w-4 h-4 text-blue-400" />
                AI-Generated Itinerary
              </span>
            </motion.div>
          </div>
        </div>

        {/* Decorative dots */}
        <div className="absolute top-4 right-4 flex gap-1.5">
          {[0, 1, 2].map(i => (
            <motion.div
              key={i}
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 0.4, scale: 1 }}
              transition={{ delay: 0.3 + i * 0.1 }}
              className="w-1.5 h-1.5 rounded-full bg-sky-400"
            />
          ))}
        </div>
      </div>
    </motion.div>
  );
}
