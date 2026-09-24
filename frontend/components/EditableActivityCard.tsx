'use client';

import { MapPin, Clock, X, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, GripVertical } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { useCurrency } from '@/lib/useCurrency';
import type { Currency } from '@/lib/currency';
import type { TimeSlot } from '@/lib/types';

interface EditableActivityCardProps {
  slot: TimeSlot;
  slotKey: 'morning' | 'afternoon' | 'evening';
  onRemove: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  onMoveLeft?: () => void;
  onMoveRight?: () => void;
  canMoveUp?: boolean;
  canMoveDown?: boolean;
  canMoveLeft?: boolean;
  canMoveRight?: boolean;
  isCustom?: boolean;
  isDragging?: boolean;
  currency?: Currency;
}

const SLOT_COLORS: Record<string, string> = {
  morning: 'text-chart-1',
  afternoon: 'text-chart-2',
  evening: 'text-chart-3',
};

const SLOT_BG: Record<string, string> = {
  morning: 'bg-chart-1/5',
  afternoon: 'bg-chart-2/5',
  evening: 'bg-chart-3/5',
};

export default function EditableActivityCard({
  slot,
  slotKey,
  onRemove,
  onMoveUp,
  onMoveDown,
  onMoveLeft,
  onMoveRight,
  canMoveUp = true,
  canMoveDown = true,
  canMoveLeft = true,
  canMoveRight = true,
  isCustom = false,
  isDragging = false,
  currency: currencyProp,
}: EditableActivityCardProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const [preferredCurrency] = useCurrency();
  const currency = currencyProp ?? preferredCurrency;
  const colorClass = SLOT_COLORS[slotKey] ?? 'text-chart-2';

  return (
    <div
      className={`group relative rounded-lg border border-border ${SLOT_BG[slotKey] ?? 'bg-muted/30'} p-2 transition-all ${isDragging ? 'opacity-50 shadow-lg ring-2 ring-primary/40' : 'hover:border-primary/30'}`}
    >
      {/* Drag handle */}
      <div className="absolute left-1 top-1/2 -translate-y-1/2 cursor-grab text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        <GripVertical className="w-3.5 h-3.5" />
      </div>

      {/* Content */}
      <div className="pl-4 pr-6">
        <p className={`text-[10px] font-medium uppercase tracking-widest ${colorClass}`}>
          {t(slotKey)}
          {isCustom && (
            <span className="ml-1.5 text-muted-foreground/60 normal-case tracking-normal">· {t('customActivity')}</span>
          )}
        </p>
        <p className="text-sm font-medium text-foreground truncate">{slot.activity}</p>
        {slot.location && (
          <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
            <MapPin className="w-3 h-3 shrink-0" />
            {slot.location}
          </p>
        )}
        <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
          {slot.duration && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {slot.duration}
            </span>
          )}
          {slot.cost_usd != null && slot.cost_usd > 0 && (
            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium ${colorClass} bg-current/5`}>
              {formatCurrency(slot.cost_usd, locale, undefined, currency)}
            </span>
          )}
        </div>
      </div>

      {/* Remove button */}
      <button
        onClick={onRemove}
        className="absolute top-1 right-1 p-0.5 rounded text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
        aria-label={t('removeActivity')}
        title={t('removeActivity')}
      >
        <X className="w-3.5 h-3.5" />
      </button>

      {/* Arrow buttons — bottom right, visible on hover (always visible on touch) */}
      <div className="absolute bottom-1 right-1 flex items-center gap-0.5 opacity-60 group-hover:opacity-100 transition-opacity">
        {canMoveLeft && onMoveLeft && (
          <button
            onClick={onMoveLeft}
            className="p-0.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
            aria-label={t('moveLeft')}
            title={t('moveLeft')}
          >
            <ChevronLeft className="w-3 h-3" />
          </button>
        )}
        {canMoveUp && onMoveUp && (
          <button
            onClick={onMoveUp}
            className="p-0.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
            aria-label={t('moveUp')}
            title={t('moveUp')}
          >
            <ChevronUp className="w-3 h-3" />
          </button>
        )}
        {canMoveDown && onMoveDown && (
          <button
            onClick={onMoveDown}
            className="p-0.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
            aria-label={t('moveDown')}
            title={t('moveDown')}
          >
            <ChevronDown className="w-3 h-3" />
          </button>
        )}
        {canMoveRight && onMoveRight && (
          <button
            onClick={onMoveRight}
            className="p-0.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
            aria-label={t('moveRight')}
            title={t('moveRight')}
          >
            <ChevronRight className="w-3 h-3" />
          </button>
        )}
      </div>
    </div>
  );
}
