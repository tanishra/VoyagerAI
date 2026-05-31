'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Globe, MapPin, Sparkles, Award } from 'lucide-react';

const stats = [
  { value: 5000, label: 'Trips Planned', icon: Globe, suffix: '+' },
  { value: 150, label: 'Destinations', icon: MapPin, suffix: '+' },
  { value: 99, label: 'Gemini Accuracy', icon: Sparkles, suffix: '%' },
  { value: 3, label: 'Years Running', icon: Award, suffix: '+' },
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
  return (
    <section className="py-16 md:py-20 border-t border-white/5">
      <div className="max-w-4xl mx-auto px-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              whileHover={{ y: -4 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="text-center group cursor-default"
            >
              <div className="inline-flex p-2.5 rounded-xl bg-white/[0.03] border border-white/5 mb-3 group-hover:scale-110 group-hover:border-sky-500/30 transition-all duration-200">
                <stat.icon className="w-5 h-5 text-sky-400" />
              </div>
              <div className="text-2xl md:text-3xl font-bold text-white tabular-nums mb-1">
                <CountUp target={stat.value} suffix={stat.suffix} />
              </div>
              <p className="text-xs text-muted-foreground">{stat.label}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
