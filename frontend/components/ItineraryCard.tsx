'use client';

import { Globe, MoreHorizontal, Printer, FileJson, FileText, Share2, Check, Map as MapIcon, ChevronDown } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import dynamic from 'next/dynamic';
import type { Itinerary } from '@/lib/types';
import { createShare, exportItinerary } from '@/lib/share-api';

const ItineraryMap = dynamic(() => import('./ItineraryMap'), { ssr: false });

interface ItineraryCardProps {
  itinerary: Itinerary;
  threadId?: string;
  printMode?: boolean;
}

export default function ItineraryCard({ itinerary, threadId, printMode = false }: ItineraryCardProps) {
  const t = useTranslations('itinerary');
  const days = itinerary.days ?? [];
  const warnings = itinerary.warnings ?? [];
  const cost: number | string = itinerary.estimated_total_cost_usd ?? 'N/A';
  const totalDays = itinerary.total_days ?? days.length;

  const [menuOpen, setMenuOpen] = useState(false);
  const [shareStatus, setShareStatus] = useState<'idle' | 'creating' | 'copied' | 'error'>('idle');
  const [mapExpanded, setMapExpanded] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  async function handleShare() {
    if (!threadId) return;
    setShareStatus('creating');
    try {
      const { share_url } = await createShare(threadId);
      await navigator.clipboard.writeText(share_url);
      setShareStatus('copied');
      setTimeout(() => setShareStatus('idle'), 2000);
    } catch {
      setShareStatus('error');
      setTimeout(() => setShareStatus('idle'), 2000);
    }
  }

  async function handleExport(format: 'json' | 'markdown') {
    if (!threadId) return;
    try {
      const blob = await exportItinerary(threadId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'json' ? 'json' : 'md';
      a.download = `${itinerary.destination?.replace(/[^a-zA-Z0-9]/g, '_') || 'itinerary'}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setMenuOpen(false);
    } catch {
      // silently fail
    }
  }

  function handlePrint() {
    if (!threadId) return;
    window.open(`/export/${threadId}`, '_blank');
    setMenuOpen(false);
  }

  return (
    <div className="mt-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5 overflow-hidden bg-card">
      <div className="px-4 py-3 border-b border-indigo-500/10 flex items-center justify-between">
        <h3 className="font-semibold text-foreground flex items-center gap-2">
          <Globe className="w-4 h-4 text-primary" />
          {itinerary.destination}
        </h3>
        {!printMode && threadId && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
              aria-label={t('exportShare')}
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border border-border bg-popover shadow-lg z-20 py-1">
                <button
                  onClick={handlePrint}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors cursor-pointer"
                >
                  <Printer className="w-3.5 h-3.5" />
                  {t('printPdf')}
                </button>
                <button
                  onClick={() => handleExport('json')}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors cursor-pointer"
                >
                  <FileJson className="w-3.5 h-3.5" />
                  {t('downloadJson')}
                </button>
                <button
                  onClick={() => handleExport('markdown')}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5" />
                  {t('downloadMarkdown')}
                </button>
                <div className="border-t border-border my-1" />
                <button
                  onClick={handleShare}
                  disabled={shareStatus === 'creating'}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors cursor-pointer disabled:opacity-50"
                >
                  {shareStatus === 'copied' ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-green-500" />
                      {t('linkCopied')}
                    </>
                  ) : shareStatus === 'creating' ? (
                    <>
                      <Share2 className="w-3.5 h-3.5 animate-pulse" />
                      {t('creatingLink')}
                    </>
                  ) : shareStatus === 'error' ? (
                    <>
                      <Share2 className="w-3.5 h-3.5 text-red-500" />
                      {t('failedToShare')}
                    </>
                  ) : (
                    <>
                      <Share2 className="w-3.5 h-3.5" />
                      {t('shareLink')}
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="p-4 space-y-3 text-sm">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className="text-muted-foreground">{t('duration')}</span>
            <p className="text-foreground font-medium">{t('days', { count: totalDays })}</p>
          </div>
          <div>
            <span className="text-muted-foreground">{t('budget')}</span>
            <p className="text-foreground font-medium">{cost === 'N/A' ? t('na') : `$${cost}`}</p>
          </div>
        </div>
        <div className="space-y-2">
          {days.map((day) => (
            <div key={day.day} className="p-2 rounded-lg bg-muted border border-border print-break-inside-avoid">
              <p className="font-medium text-foreground">
                {t('dayN', { n: day.day })} — {day.theme ?? t('dayN', { n: day.day })}
              </p>
              <p className="text-muted-foreground text-xs mt-0.5">
                {day.morning?.activity ?? '—'} → {day.afternoon?.activity ?? '—'} → {day.evening?.activity ?? '—'}
              </p>
              {!printMode && (
                <div className="mt-1.5 text-xs text-muted-foreground space-y-0.5">
                  <p>{t('transport')}: {day.transport ?? t('na')}</p>
                  <p>{t('stay')}: {day.accommodation ?? t('na')}</p>
                  <p>{t('dailyCost')}: ${day.daily_cost_usd ?? t('na')}</p>
                  {day.tips && day.tips.length > 0 && (
                    <p className="text-amber-600">💡 {day.tips[0]}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
        {/* Map section — hidden in print mode */}
        {!printMode && (
          <div className="print-hidden">
            <button
              onClick={() => setMapExpanded(!mapExpanded)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-muted border border-border text-sm text-foreground hover:bg-muted/80 transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-2">
                <MapIcon className="w-4 h-4 text-primary" />
                {t('map')}
              </span>
              <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${mapExpanded ? 'rotate-180' : ''}`} />
            </button>
            {mapExpanded && (
              <div className="mt-2">
                <ItineraryMap days={days} destination={itinerary.destination} />
              </div>
            )}
          </div>
        )}
        {warnings.length > 0 && (
          <div className="text-xs text-amber-600">
            ⚠ {warnings[0]}
          </div>
        )}
        {printMode && itinerary.packing_essentials && itinerary.packing_essentials.length > 0 && (
          <div className="pt-2 border-t border-border">
            <p className="text-muted-foreground font-medium mb-1">🎒 {t('packingEssentials')}</p>
            <ul className="text-xs text-muted-foreground list-disc list-inside">
              {itinerary.packing_essentials.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
