'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

interface TextGenerateProps {
  text: string;
  className?: string;
  duration?: number;
  delay?: number;
}

export function TextGenerate({
  text,
  className = '',
  duration = 0.8,
  delay = 0,
}: TextGenerateProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <motion.span
      ref={ref}
      initial={{ opacity: 0, filter: 'blur(8px)' }}
      animate={isInView ? { opacity: 1, filter: 'blur(0px)' } : {}}
      transition={{ duration, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {text}
    </motion.span>
  );
}
