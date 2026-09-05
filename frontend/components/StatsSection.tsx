'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';

const stats = [
  { value: 5000, label: 'statsTrips', suffix: '+' },
  { value: 150, label: 'statsDestinations', suffix: '+' },
  { value: 99, label: 'statsAccuracy', suffix: '%' },
  { value: 3, label: 'statsYears', suffix: '+' },
];

function CountUp({ target, suffix }: { target: number; suffix: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const counted = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !counted.current) {
          counted.current = true;
          const duration = 1500;
          const steps = 30;
          const increment = target / steps;
          let current = 0;
          const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
              setCount(target);
              clearInterval(timer);
            } else {
              setCount(Math.floor(current));
            }
          }, duration / steps);
        }
      },
      { threshold: 0.3 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target]);

  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}

export default function StatsSection() {
  const t = useTranslations('home');
  return (
    <section className="py-20 md:py-24 border-t border-border">
      <div className="max-w-4xl mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="bg-background py-8 px-4 text-center"
            >
              <div className="text-3xl md:text-4xl font-bold text-foreground tabular-nums mb-2">
                <CountUp target={stat.value} suffix={stat.suffix} />
              </div>
              <p className="text-xs text-muted-foreground tracking-wide">
                {t(stat.label)}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
