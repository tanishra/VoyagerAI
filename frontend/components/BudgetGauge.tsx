'use client';

import { motion } from 'framer-motion';

interface BudgetGaugeProps {
  percent: number;
  status: 'within' | 'over' | 'under';
  size?: number;
}

const statusColors = {
  within: { stroke: '#10B981', track: 'rgba(16, 185, 129, 0.15)', text: 'text-emerald-400' },
  over: { stroke: '#EF4444', track: 'rgba(239, 68, 68, 0.15)', text: 'text-red-400' },
  under: { stroke: '#F59E0B', track: 'rgba(245, 158, 11, 0.15)', text: 'text-amber-400' },
};

export default function BudgetGauge({ percent, status, size = 120 }: BudgetGaugeProps) {
  const colors = statusColors[status];
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(percent, 100) / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={`Budget usage at ${percent}%`}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors.track}
          strokeWidth="6"
        />
        {/* Progress */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth="6"
          strokeLinecap="round"
          initial={{ strokeDasharray: circumference, strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: 'easeOut', delay: 0.3 }}
          style={{ strokeDasharray: circumference }}
        />
      </svg>

      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.6, type: 'spring', stiffness: 200 }}
          className={`text-xl font-bold tabular-nums ${colors.text}`}
        >
          {Math.min(percent, 100)}%
        </motion.span>
        <span className="text-[10px] text-muted-foreground -mt-0.5">used</span>
      </div>
    </div>
  );
}
