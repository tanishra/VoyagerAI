'use client';

import { motion } from 'framer-motion';
import { Sparkles, ArrowRight } from 'lucide-react';
import { getLoginUrl } from '@/lib/auth';

export default function LoginPage() {
  return (
    <main className="relative min-h-screen overflow-hidden pt-16">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-indigo-400/[0.06] rounded-full blur-[120px] animate-aurora" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-violet-400/[0.04] rounded-full blur-[100px] animate-float-slow" />
      </div>

      <div className="relative z-10 max-w-md mx-auto px-4 pt-20 pb-12">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="text-center"
        >
          <div className="flex items-center justify-center gap-2.5 mb-6">
            <motion.div
              animate={{ rotate: [0, 10, -10, 0] }}
              transition={{ repeat: Infinity, duration: 6, ease: 'easeInOut' }}
              className="p-2 rounded-xl bg-gradient-to-br from-indigo-500/10 to-violet-500/10 border border-indigo-500/15"
            >
              <Sparkles className="w-6 h-6 text-primary" />
            </motion.div>
            <h1 className="text-3xl font-bold text-foreground">VoyagerAI</h1>
          </div>

          <p className="text-sm text-muted-foreground mb-8 max-w-xs mx-auto">
            Sign in to start planning your trips with AI-powered itineraries.
          </p>

          <a
            href={getLoginUrl()}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all duration-200 hover:shadow-lg hover:shadow-primary/20"
          >
            Sign in with Google
            <ArrowRight className="w-4 h-4" />
          </a>

          <p className="text-xs text-muted-foreground mt-6">
            By signing in, you agree to let VoyagerAI access your Google email and profile.
          </p>
        </motion.div>
      </div>
    </main>
  );
}
