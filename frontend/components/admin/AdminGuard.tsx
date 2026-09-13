'use client';

import { useState, useEffect } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { getSession } from '@/lib/auth';

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<'loading' | 'denied' | 'ok'>('loading');

  useEffect(() => {
    getSession().then((user) => {
      if (!user) {
        window.location.href = '/login';
        return;
      }
      setState(user.is_admin ? 'ok' : 'denied');
    });
  }, []);

  if (state === 'loading') {
    return (
      <main className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </main>
    );
  }

  if (state === 'denied') {
    return (
      <main className="min-h-screen flex items-center justify-center bg-background p-4">
        <div className="text-center max-w-sm">
          <span className="block w-3 h-0.5 bg-primary mx-auto mb-6" />
          <AlertCircle className="w-10 h-10 text-destructive mx-auto mb-4" />
          <h1 className="text-xl font-bold text-foreground mb-2">Access Denied</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Admin privileges are required to view this page.
          </p>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Back to home
          </Link>
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
