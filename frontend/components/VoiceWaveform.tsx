'use client';

import { motion } from 'framer-motion';

interface VoiceWaveformProps {
  isActive: boolean;
}

const BARS = [0, 1, 2, 3, 4, 5, 6];

export default function VoiceWaveform({ isActive }: VoiceWaveformProps) {
  if (!isActive) return null;

  return (
    <div className="flex items-center gap-0.5 h-6 px-1" aria-hidden="true">
      {BARS.map((i) => (
        <motion.div
          key={i}
          className="w-1 rounded-full bg-red-500"
          animate={{
            height: [4, 20, 4],
          }}
          transition={{
            duration: 0.6,
            repeat: Infinity,
            repeatType: 'reverse',
            delay: i * 0.08,
            ease: 'easeInOut',
          }}
          style={{ height: 4 }}
        />
      ))}
    </div>
  );
}
