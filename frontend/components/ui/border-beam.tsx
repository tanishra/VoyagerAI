'use client';

import { motion } from 'framer-motion';

interface BorderBeamProps {
  className?: string;
  duration?: number;
  delay?: number;
}

export function BorderBeam({
  className = '',
  duration = 3,
  delay = 0,
}: BorderBeamProps) {
  return (
    <motion.div
      className={`pointer-events-none absolute inset-0 rounded-[inherit] overflow-hidden ${className}`}
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
    >
      <motion.div
        className="absolute -inset-[100%] w-[200%] h-[200%]"
        style={{
          background:
            'conic-gradient(from 0deg, transparent 0deg, var(--primary) 60deg, transparent 120deg, transparent 360deg)',
          opacity: 0.3,
        }}
        animate={{ rotate: 360 }}
        transition={{ duration, delay, repeat: Infinity, ease: 'linear' }}
      />
    </motion.div>
  );
}
