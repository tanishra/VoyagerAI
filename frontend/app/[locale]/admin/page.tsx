'use client';

import { useState } from 'react';
import { ArrowLeft, AlertCircle, DollarSign, Shield, ListTree, GitBranch, BarChart3 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
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

export default function AdminPage() {
  const t = useTranslations('admin');
  const [activeTab, setActiveTab] = useState<Tab>('sessions');
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);

  function handleSelectSession(threadId: string) {
    setSelectedThreadId(threadId);
    setActiveTab('trace');
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-neutral-400 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-bold">{t('title')}</h1>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 mb-6 border-b border-neutral-800 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
                activeTab === tab.id
                  ? 'border-blue-500 text-white'
                  : 'border-transparent text-neutral-400 hover:text-white'
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
