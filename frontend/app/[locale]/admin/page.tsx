'use client';

import { useState } from 'react';
import { ArrowLeft, AlertCircle, DollarSign, Shield, ListTree, GitBranch, BarChart3 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { AdminGuard } from '@/components/admin/AdminGuard';
import { SessionsTable } from '@/components/admin/SessionsTable';
import { TraceWaterfall } from '@/components/admin/TraceWaterfall';
import { ErrorsPanel } from '@/components/admin/ErrorsPanel';
import { UsagePanel } from '@/components/admin/UsagePanel';
import { CostsTab } from '@/components/admin/CostsTab';
import { SecurityTab } from '@/components/admin/SecurityTab';

type Tab = 'sessions' | 'trace' | 'errors' | 'costs' | 'security' | 'usage';

const TABS: { id: Tab; icon: React.ReactNode; labelKey: string }[] = [
  { id: 'sessions', icon: <ListTree className="w-4 h-4" />, labelKey: 'tabSessions' },
  { id: 'trace', icon: <GitBranch className="w-4 h-4" />, labelKey: 'tabTrace' },
  { id: 'errors', icon: <AlertCircle className="w-4 h-4" />, labelKey: 'tabErrors' },
  { id: 'usage', icon: <BarChart3 className="w-4 h-4" />, labelKey: 'tabUsage' },
  { id: 'costs', icon: <DollarSign className="w-4 h-4" />, labelKey: 'tabCosts' },
  { id: 'security', icon: <Shield className="w-4 h-4" />, labelKey: 'tabSecurity' },
];

function AdminContent() {
  const t = useTranslations('admin');
  const [activeTab, setActiveTab] = useState<Tab>('sessions');
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);

  function handleSelectSession(threadId: string) {
    setSelectedThreadId(threadId);
    setActiveTab('trace');
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-6 pt-20">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <span className="w-1 h-6 bg-primary rounded-full" />
            <h1 className="text-2xl font-bold tracking-tight">{t('title')}</h1>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 mb-6 border-b border-border overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.icon}
              {t(tab.labelKey)}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div>
          {activeTab === 'sessions' && (
            <SessionsTable onSelectSession={handleSelectSession} />
          )}
          {activeTab === 'trace' && (
            <TraceWaterfall threadId={selectedThreadId} />
          )}
          {activeTab === 'errors' && <ErrorsPanel />}
          {activeTab === 'usage' && <UsagePanel />}
          {activeTab === 'costs' && <CostsTab />}
          {activeTab === 'security' && <SecurityTab />}
        </div>
      </div>
    </div>
  );
}

export default function AdminPage() {
  return (
    <AdminGuard>
      <AdminContent />
    </AdminGuard>
  );
}
