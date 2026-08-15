'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, X, Sparkles, ArrowRight, LogOut, ChevronDown } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { getSession, logout, getLoginUrl, type SessionUser } from '@/lib/auth';
import { useLocale } from '@/lib/useLocale';
import InstallPrompt from './InstallPrompt';
import LanguageSwitcher from './LanguageSwitcher';

const navLinkKeys = ['home', 'chat', 'preferences', 'about'] as const;
const navHrefs: Record<string, string> = {
  home: '',
  chat: '/chat',
  preferences: '/preferences',
  about: '/about',
};

function Avatar({ user, size = 'sm' }: { user: SessionUser; size?: 'sm' | 'md' }) {
  const dims = size === 'md' ? 'w-9 h-9' : 'w-7 h-7';
  const text = size === 'md' ? 'text-sm' : 'text-xs';
  if (user.avatar_url) {
    return (
      <Image
        src={user.avatar_url}
        alt={user.display_name}
        width={size === 'md' ? 36 : 28}
        height={size === 'md' ? 36 : 28}
        className={`${dims} rounded-full object-cover border border-border`}
      />
    );
  }
  const initials = user.display_name
    .split(' ')
    .map(w => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  return (
    <div className={`${dims} rounded-full bg-primary/10 flex items-center justify-center ${text} font-semibold text-primary`}>
      {initials || '?'}
    </div>
  );
}

export default function Navbar() {
  const t = useTranslations('nav');
  const locale = useLocale();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [userLoading, setUserLoading] = useState(true);
  const pathname = usePathname();
  const router = useRouter();
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setMenuOpen(false));
    return () => cancelAnimationFrame(raf);
  }, [pathname]);

  useEffect(() => {
    getSession().then((u) => {
      setUser(u);
      setUserLoading(false);
    });
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  async function handleLogout() {
    await logout();
    setUser(null);
    setUserMenuOpen(false);
    router.push(`/${locale}/login`);
  }

  const isDevUser = user?.user_id === 'dev@localhost';

  return (
    <nav
      className={`fixed top-0 inset-x-0 z-50 transition-all duration-500 ${
        scrolled
          ? 'bg-white/80 backdrop-blur-xl border-b border-border shadow-sm'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link
          href={`/${locale}`}
          className="flex items-center gap-2 font-bold text-lg text-foreground hover:text-primary transition-colors"
        >
          <div className="p-1.5 rounded-lg bg-gradient-to-br from-indigo-500/10 to-violet-500/10 border border-indigo-500/15">
            <Sparkles className="w-4 h-4 text-primary" />
          </div>
          {t('brand')}
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center gap-1">
          {navLinkKeys.map(key => {
            const href = key === 'home' ? `/${locale}` : `/${locale}${navHrefs[key]}`;
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`relative px-4 py-2 text-sm rounded-lg transition-all duration-200 ${
                  active
                    ? 'text-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                }`}
              >
                {t(key)}
                {active && (
                  <motion.div
                    layoutId="nav-active"
                    className="absolute inset-0 rounded-lg bg-primary/8 -z-10"
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
              </Link>
            );
          })}

          {/* Auth section */}
          {!userLoading && user ? (
            <div className="relative ml-2" ref={userMenuRef}>
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-muted transition-colors cursor-pointer"
              >
                <Avatar user={user} />
                <span className="text-sm font-medium text-foreground max-w-[120px] truncate">
                  {user.display_name}
                </span>
                {isDevUser && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 font-medium">
                    Dev
                  </span>
                )}
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              </button>
              <AnimatePresence>
                {userMenuOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-border bg-white shadow-lg overflow-hidden"
                  >
                    <div className="px-4 py-3 border-b border-border">
                      <p className="text-sm font-medium text-foreground truncate">{user.display_name}</p>
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    </div>
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors cursor-pointer"
                    >
                      <LogOut className="w-4 h-4" />
                      {t('signOut')}
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ) : !userLoading ? (
            <a
              href={getLoginUrl()}
              className="ml-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all duration-200 hover:shadow-md hover:shadow-primary/20"
            >
              {t('signIn')}
              <ArrowRight className="w-3.5 h-3.5" />
            </a>
          ) : null}
          <LanguageSwitcher />
          <InstallPrompt />
        </div>

        {/* Mobile Toggle */}
        <div className="md:hidden">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-2 text-muted-foreground hover:text-foreground cursor-pointer"
            aria-label={menuOpen ? t('closeMenu') : t('openMenu')}
          >
            {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden overflow-hidden border-t border-border bg-white/95 backdrop-blur-xl"
          >
            <div className="px-4 py-3 space-y-1">
              {navLinkKeys.map(key => {
                const href = key === 'home' ? `/${locale}` : `/${locale}${navHrefs[key]}`;
                const active = pathname === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`block px-4 py-2.5 text-sm rounded-lg transition-all ${
                      active
                        ? 'text-primary bg-primary/8'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    }`}
                  >
                    {t(key)}
                  </Link>
                );
              })}
              {!userLoading && user ? (
                <div className="pt-3 mt-2 border-t border-border">
                  <div className="flex items-center gap-3 px-4 py-2">
                    <Avatar user={user} size="md" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-foreground truncate">{user.display_name}</p>
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    </div>
                    {isDevUser && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 font-medium">
                        Dev
                      </span>
                    )}
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-foreground hover:bg-muted rounded-lg transition-colors cursor-pointer"
                  >
                    <LogOut className="w-4 h-4" />
                    {t('signOut')}
                  </button>
                </div>
              ) : !userLoading ? (
                <a
                  href={getLoginUrl()}
                  className="block mt-2 px-4 py-2.5 text-sm rounded-lg bg-primary text-primary-foreground font-medium text-center"
                >
                  {t('signInWithGoogle')} →
                </a>
              ) : null}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
