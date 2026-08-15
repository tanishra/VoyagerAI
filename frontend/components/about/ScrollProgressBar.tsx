'use client';

import { motion, useScroll, useSpring } from 'framer-motion';

export default function ScrollProgressBar() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 20,
    mass: 0.2,
  });

  return (
    <motion.div
      style={{ scaleX, transformOrigin: '0% 0%' }}
      className="fixed top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-indigo-500 to-violet-500 z-[60]"
    />
  );
}
