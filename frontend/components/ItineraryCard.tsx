'use client';

import { MoreHorizontal, Printer, FileText, Share2, Check, Map as MapIcon, ChevronDown, Calendar, Pencil, ExternalLink, AlertTriangle, PencilRuler } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import dynamic from 'next/dynamic';
import useSWR from 'swr';
import type { Itinerary } from '@/lib/types';
import { createShare, exportItinerary } from '@/lib/share-api';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { asCurrency } from '@/lib/currency';
import { fetchWikimediaImage } from '@/lib/wikimedia';
import DayDetailPanel from './DayDetailPanel';
import TimelineView from './TimelineView';
import BudgetStatus from './BudgetStatus';
import { useCurrency } from '@/lib/useCurrency';
import ItineraryEditor from './ItineraryEditor';

const ItineraryMap = dynamic(() => import('./ItineraryMap'), { ssr: false });

interface ItineraryCardProps {
  itinerary: Itinerary;
  threadId?: string;
  printMode?: boolean;
  onEditItinerary?: (modifiedItinerary: Itinerary) => void;
}

export default function ItineraryCard({ itinerary, threadId, printMode = false, onEditItinerary }: ItineraryCardProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const days = itinerary.days ?? [];
  const warnings = itinerary.warnings ?? [];
  const cost: number | null = itinerary.estimated_total_cost_usd ?? null;
  const totalDays = itinerary.total_days ?? days.length;

  const [menuOpen, setMenuOpen] = useState(false);
  const [shareStatus, setShareStatus] = useState<'idle' | 'creating' | 'copied' | 'error'>('idle');
  const [mapExpanded, setMapExpanded] = useState(false);
  const [panelDay, setPanelDay] = useState<number | null>(null);
  const [showEditChanges, setShowEditChanges] = useState(false);
  const [editing, setEditing] = useState(false);
  const [preferredCurrency] = useCurrency();
  // The itinerary's own currency (what the numbers are actually expressed
  // in) always wins over the app-wide preference — otherwise the symbol
  // shown can silently disagree with the values behind it.
  const currency = asCurrency(itinerary.currency) ?? preferredCurrency;
  const menuRef = useRef<HTMLDivElement>(null);

  const { data: destImage, isLoading: destImageLoading } = useSWR(
    `wikimedia:${itinerary.destination}`,
    () => fetchWikimediaImage(itinerary.destination),
    { revalidateOnFocus: false, dedupingInterval: 600000 }
  );

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

  async function handleExport(format: 'markdown' | 'ical') {
    if (!threadId) return;
    try {
      const blob = await exportItinerary(threadId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'markdown' ? 'md' : 'ics';
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
    window.open(`/${locale}/export/${threadId}`, '_blank');
    setMenuOpen(false);
  }

  async function handleOpenSharePage() {
    if (!threadId) return;
    try {
      const { share_url } = await createShare(threadId);
      window.open(share_url, '_blank');
    } catch {
      // silently fail
    }
    setMenuOpen(false);
  }

  return (
    <div className="mt-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5 overflow-hidden bg-card">
      {/* Destination banner image */}
      <div className="relative w-full" style={{ aspectRatio: '16 / 6' }}>
        {destImageLoading ? (
          <div className="w-full h-full animate-pulse bg-muted" />
        ) : destImage ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={destImage} alt={itinerary.destination} className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
            <h3 className="absolute bottom-3 left-4 text-xl font-bold text-white drop-shadow-lg">
              {itinerary.destination}
            </h3>
          </>
        ) : (
          <div className="w-full h-full bg-accent flex items-center justify-center">
            <span className="text-2xl font-bold text-accent-foreground tracking-tight">
              {itinerary.destination}
            </span>
          </div>
        )}
      </div>
      {/* Limited-research badge — plan built while a specialist failed */}
      {itinerary.research_limited && (
        <div className="flex items-center gap-2 px-4 py-2 border-b border-indigo-500/10 bg-amber-500/10 text-amber-700 dark:text-amber-400 text-xs">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>{t('limitedResearch')}</span>
        </div>
      )}
      {/* Edit-diff strip — what the validator changed after a manual edit */}
      {(itinerary.edit_changes?.length ?? 0) > 0 && (
        <div className="px-4 py-2 border-b border-indigo-500/10 bg-muted/40 text-xs">
          <button
            onClick={() => setShowEditChanges((v) => !v)}
            className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            aria-expanded={showEditChanges}
          >
            <PencilRuler className="w-3.5 h-3.5" />
            <span>{t('editChangesTitle', { count: itinerary.edit_changes!.length })}</span>
            <ChevronDown className={`w-3 h-3 transition-transform ${showEditChanges ? 'rotate-180' : ''}`} />
          </button>
          {showEditChanges && (
            <ul className="mt-1.5 space-y-1 text-muted-foreground">
              {itinerary.edit_changes!.map((c, i) => (
                <li key={i}>
                  {c.type === 'cost'
                    ? t('editChange.cost', {
                        before: formatCurrency(c.before ?? 0, locale, undefined, currency),
                        after: formatCurrency(c.after ?? 0, locale, undefined, currency),
                      })
                    : t(`editChange.${c.type}`, {
                        day: c.day ?? '',
                        slot: c.slot ? t(c.slot) : '',
                        activity: c.activity ?? '',
                        detail: c.detail ?? '',
                      })}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <div className="px-4 py-3 border-b border-indigo-500/10 flex items-center justify-end">
        {!printMode && threadId && (
          <div className="flex items-center gap-1">
          {onEditItinerary && (
            <button
              onClick={() => setEditing(true)}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
              aria-label={t('editItinerary')}
              title={t('editItinerary')}
            >
              <Pencil className="w-4 h-4" />
            </button>
          )}
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
                  onClick={() => handleExport('markdown')}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5" />
                  {t('downloadMarkdown')}
                </button>
                <button
                  onClick={() => handleExport('ical')}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors cursor-pointer"
                >
                  <Calendar className="w-3.5 h-3.5" />
                  {t('addToCalendar')}
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
                <button
                  onClick={handleOpenSharePage}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors cursor-pointer"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  {t('openSharePage')}
                </button>
              </div>
            )}
          </div>
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
            <div className="flex items-center gap-2">
              <p className="text-foreground font-medium">{cost === null ? t('na') : formatCurrency(cost, locale, undefined, currency)}</p>
              <BudgetStatus status={itinerary.budget_status} totalCost={cost} currency={currency} />
            </div>
          </div>
        </div>
        {!printMode ? (
          <TimelineView
            days={days}
            destination={itinerary.destination}
            currency={currency}
            onDayClick={(day) => setPanelDay(day.day)}
          />
        ) : (
          <div className="space-y-2">
            {days.map((day) => (
              <div key={day.day} className="p-2 rounded-lg bg-muted border border-border print-break-inside-avoid">
                <p className="font-medium text-foreground">
                  {t('dayN', { n: day.day })} — {day.theme ?? t('dayN', { n: day.day })}
                </p>
                <p className="text-muted-foreground text-xs mt-0.5">
                  {(['morning', 'afternoon', 'evening'] as const).map((k) => {
                    const slot = day[k];
                    return slot?.time ? `${slot.time} ${slot.activity}` : (slot?.activity ?? '—');
                  }).join(' → ')}
                </p>
                <div className="mt-1.5 text-xs text-muted-foreground space-y-0.5">
                  <p>{t('transport')}: {day.transport ?? t('na')}</p>
                  <p>{t('stay')}: {day.accommodation ?? t('na')}</p>
                  <p>{t('dailyCost')}: {day.daily_cost_usd != null ? formatCurrency(day.daily_cost_usd, locale, undefined, currency) : t('na')}</p>
                  {day.tips && day.tips.length > 0 && (
                    <div className="space-y-0.5">
                      {day.tips.map((tip, i) => (
                        <p key={i} className="text-accent-foreground">💡 {tip}</p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
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
                <ItineraryMap
                  days={days}
                  destination={itinerary.destination}
                  currency={currency}
                  activeDay={panelDay}
                  onMarkerClick={(day) => setPanelDay(day)}
                  onDaySelect={(day) => setPanelDay(day)}
                />
              </div>
            )}
          </div>
        )}
        {warnings.length > 0 && (
          <div className="text-xs space-y-1 pt-2 border-t border-border">
            {warnings.map((w, i) => (
              <p key={i} className="text-accent-foreground">⚠ {w}</p>
            ))}
          </div>
        )}
        {itinerary.packing_essentials && itinerary.packing_essentials.length > 0 && (
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
      {panelDay !== null && (
        <DayDetailPanel
          days={days}
          destination={itinerary.destination}
          currency={currency}
          initialDay={panelDay}
          onClose={() => setPanelDay(null)}
        />
      )}
      {editing && threadId && onEditItinerary && (
        <ItineraryEditor
          itinerary={itinerary}
          threadId={threadId}
          onClose={() => setEditing(false)}
          onSave={(modified) => {
            onEditItinerary(modified);
            setEditing(false);
          }}
        />
      )}
    </div>
  );
}
