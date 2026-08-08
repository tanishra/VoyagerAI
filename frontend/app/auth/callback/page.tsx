'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { getSession } from '@/lib/auth';
import { Loader2, AlertCircle } from 'lucide-react';
import Link from 'next/link';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialSuccess = searchParams.get('success') === '1';
  const [error, setError] = useState(!initialSuccess);

  useEffect(() => {
    if (!initialSuccess) return;

    let cancelled = false;
    getSession().then((user) => {
      if (cancelled) return;
      if (user) {
        router.push('/chat');
      } else {
        setError(true);
      }
    });
    return () => { cancelled = true; };
  }, [router, initialSuccess]);

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
