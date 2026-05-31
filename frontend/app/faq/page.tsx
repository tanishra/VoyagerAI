'use client';

import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import FaqSection from '@/components/FaqSection';

export default function FaqPage() {
  return (
    <main className="relative min-h-screen pt-24 pb-16">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-blue-500/[0.05] rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10 max-w-3xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-medium mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            FAQ
          </div>
          <h1 className="text-3xl md:text-5xl font-bold text-white mb-4">
            Frequently Asked Questions
          </h1>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Everything you need to know about AI-powered trip planning
          </p>
        </motion.div>

        <FaqSection />
      </div>
    </main>
  );
}
