'use client';

import { motion } from 'framer-motion';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useLocale } from '@/lib/useLocale';
import { getLoginUrl, getSession } from '@/lib/auth';
import GoogleIcon from '@/components/GoogleIcon';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const t = useTranslations('auth');
  const tNav = useTranslations('nav');
  const locale = useLocale();
  const router = useRouter();

  // Already signed in → skip the login card entirely
  useEffect(() => {
    getSession().then((user) => {
      if (user) router.replace(`/${locale}/chat`);
    });
  }, [router, locale]);

  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* Full-bleed destination photograph */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/destinations/kyoto-autumn.webp"
          alt="Kyoto autumn temple"
          fill
          priority
          sizes="100vw"
          className="object-cover"
        />
        {/* Dark gradient overlay for legibility */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/50 via-black/40 to-black/60" />
      </div>

      {/* Back to home button */}
      <Link
        href={`/${locale}`}
        className="absolute top-6 left-6 z-20 inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-white/80 hover:text-white bg-black/20 hover:bg-black/30 backdrop-blur-md transition-all duration-200"
      >
        <ArrowLeft className="w-4 h-4" />
        {tNav('home')}
      </Link>

      {/* Centered frosted glass card */}
      <div className="relative z-10 min-h-screen flex items-center justify-center px-4 py-16">
        <motion.div
          initial={{ opacity: 0, y: 20, filter: 'blur(8px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0)' }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-md rounded-2xl border border-border bg-card/80 backdrop-blur-xl shadow-2xl overflow-hidden"
        >
          {/* Cinnabar hairline accent at top */}
          <div className="h-px w-full bg-primary/40" />

          <div className="px-8 py-10 flex flex-col items-center text-center">
            {/* Brand mark */}
            <div className="flex items-center gap-2.5 mb-8">
              <span className="w-1 h-7 bg-primary rounded-full" />
              <h1 className="text-2xl font-bold text-foreground tracking-tight">{tNav('brand')}</h1>
            </div>

            {/* Editorial headline */}
            <motion.h2
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
              className="text-3xl sm:text-4xl font-bold leading-[1.1] mb-4 tracking-tight text-foreground"
            >
              {t('loginHeadline')}
              <br />
              <span className="text-primary italic font-semibold">
                {t('loginHeadlineAccent')}
              </span>
            </motion.h2>

            {/* Supporting description */}
            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
              className="text-sm text-muted-foreground max-w-xs mb-8 leading-relaxed"
            >
              {t('loginSubtext')}
            </motion.p>

            {/* Google sign-in button */}
            <motion.a
              href={getLoginUrl()}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="group inline-flex items-center gap-3 w-full justify-center px-6 py-3.5 rounded-lg bg-primary text-primary-foreground text-sm font-semibold transition-all duration-300 hover:bg-primary/90 hover:-translate-y-0.5 shadow-lg"
            >
              <GoogleIcon className="w-5 h-5" />
              {t('signInWithGoogle')}
            </motion.a>

            {/* Privacy note */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.7, delay: 0.6 }}
              className="text-xs text-muted-foreground/70 mt-6 max-w-xs"
            >
              {t('privacyNote')}
            </motion.p>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
