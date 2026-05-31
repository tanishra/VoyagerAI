'use client';

import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import Link from 'next/link';

const footerLinks = [
  { href: '/plan', label: 'Plan Trip' },
  { href: '/about', label: 'About' },
  { href: '/faq', label: 'FAQ' },
];

export default function Footer() {
  return (
    <footer className="border-t border-white/5 bg-black/40 backdrop-blur-sm">
      <div className="max-w-6xl mx-auto px-4 py-8 md:py-10">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="flex flex-col md:flex-row items-center justify-between gap-6"
        >
          <Link href="/" className="flex items-center gap-2 text-white font-bold hover:scale-105 transition-transform">
            <div className="p-1 rounded-lg bg-gradient-to-br from-sky-500/20 to-blue-500/20 border border-sky-500/15">
              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
            </div>
            VoyagerAI
          </Link>

          <div className="flex items-center gap-6">
            {footerLinks.map(link => (
              <Link
                key={link.href}
                href={link.href}
                className="text-xs text-white/40 hover:text-white/70 hover:translate-y-[-1px] transition-all duration-200"
              >
                {link.label}
              </Link>
            ))}
          </div>

          <p className="text-xs text-white/30">
            Built with Gemini &middot; Powered by Google Gen AI
          </p>
        </motion.div>
      </div>
    </footer>
  );
}
