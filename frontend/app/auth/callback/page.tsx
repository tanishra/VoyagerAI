'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { getSession, clearSessionCache } from '@/lib/auth';
import { setSessionToken } from '@/lib/session-token';
import { Loader2, AlertCircle } from 'lucide-react';
import Link from 'next/link';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialSuccess = searchParams.get('success') === '1';
  const token = searchParams.get('token');
  const [error, setError] = useState(!initialSuccess);

  useEffect(() => {
    if (!initialSuccess) return;

    // Store session token from URL for cross-domain auth (fallback when cookies are blocked)
    if (token) {
      console.log('[auth/callback] Storing session token from URL');
      setSessionToken(token);
      clearSessionCache();
      // Clean the token from the URL for security
      window.history.replaceState({}, '', '/auth/callback?success=1');
    } else {
      console.log('[auth/callback] No token in URL — relying on cookie only');
    }

    let cancelled = false;
    console.log('[auth/callback] Calling getSession()...');
    getSession().then((user) => {
      if (cancelled) return;
      console.log('[auth/callback] getSession result:', user);
      if (user) {
        router.push('/chat');
      } else {
        setError(true);
      }
    }).catch((err) => {
      console.error('[auth/callback] getSession error:', err);
      setError(true);
    });
    return () => { cancelled = true; };
  }, [router, initialSuccess, token]);

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-sm">
          <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-foreground mb-2">Sign-in failed</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Something went wrong during authentication. Please try again.
          </p>
          <Link
            href="/login"
            className="inline-flex items-center px-5 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Try again
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin mx-auto mb-3" />
        <p className="text-sm text-muted-foreground">Signing you in...</p>
      </div>
    </main>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-primary animate-spin" />
        </main>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}
