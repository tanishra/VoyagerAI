'use client';

import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useTranslations } from 'next-intl';

const footerLinks = [
  { href: '/chat', key: 'chat' },
  { href: '/about', key: 'about' },
  { href: '/faq', key: 'faq' },
];

export default function Footer() {
  const t = useTranslations('footer');
  const tNav = useTranslations('nav');
  return (
    <footer className="border-t border-border bg-muted/50 backdrop-blur-sm">
      <div className="max-w-6xl mx-auto px-4 py-8 md:py-10">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="flex flex-col md:flex-row items-center justify-between gap-6"
        >
          <Link href="/" className="flex items-center gap-2 text-foreground font-bold hover:text-primary transition-colors">
            <div className="p-1 rounded-lg bg-gradient-to-br from-indigo-500/10 to-violet-500/10 border border-indigo-500/15">
              <Sparkles className="w-3.5 h-3.5 text-primary" />
            </div>
            {tNav('brand')}
          </Link>

          <div className="flex items-center gap-6">
            {footerLinks.map(link => (
              <Link
                key={link.href}
                href={link.href}
                className="text-xs text-muted-foreground hover:text-foreground hover:translate-y-[-1px] transition-all duration-200"
              >
                {t(link.key)}
              </Link>
            ))}
          </div>

          <p className="text-xs text-muted-foreground/60">
            {t('tagline')}
          </p>
        </motion.div>
      </div>
    </footer>
  );
}
