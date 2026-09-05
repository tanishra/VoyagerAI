'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { useLocale } from '@/lib/useLocale';

const footerLinks = [
  { href: '/chat', key: 'chat' },
  { href: '/about', key: 'about' },
];

export default function Footer() {
  const t = useTranslations('footer');
  const tNav = useTranslations('nav');
  const locale = useLocale();
  return (
    <footer className="border-t border-border bg-muted/30">
      <div className="max-w-6xl mx-auto px-6 py-8 md:py-10">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="flex flex-col md:flex-row items-center justify-between gap-6"
        >
          <Link href={`/${locale}`} className="flex items-center gap-2.5 text-foreground font-bold hover:text-primary transition-colors tracking-tight">
            <span className="w-1 h-4 bg-primary rounded-full" />
            {tNav('brand')}
          </Link>

          <div className="flex items-center gap-6">
            {footerLinks.map(link => (
              <Link
                key={link.href}
                href={`/${locale}${link.href}`}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors duration-200"
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
