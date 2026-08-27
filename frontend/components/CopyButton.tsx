'use client';

import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { useTranslations } from 'next-intl';
import type { Itinerary, ComparisonData, DayPlan } from '@/lib/types';

export function formatItineraryText(itinerary: Itinerary): string {
  const lines: string[] = [];
  const cost = itinerary.estimated_total_cost_usd != null
    ? `$${itinerary.estimated_total_cost_usd.toLocaleString()}`
    : 'N/A';

  lines.push(`📍 ${itinerary.destination} — ${itinerary.total_days} days — ${cost}`);
  lines.push('');

  for (const day of itinerary.days ?? []) {
    lines.push(`Day ${day.day}: ${day.theme ?? `Day ${day.day}`}`);
    if (day.morning?.activity) {
      lines.push(`  Morning: ${day.morning.activity} (${day.morning.duration ?? ''}, $${day.morning.cost_usd ?? 0})`);
    }
    if (day.afternoon?.activity) {
      lines.push(`  Afternoon: ${day.afternoon.activity} (${day.afternoon.duration ?? ''}, $${day.afternoon.cost_usd ?? 0})`);
    }
    if (day.evening?.activity) {
      lines.push(`  Evening: ${day.evening.activity} (${day.evening.duration ?? ''}, $${day.evening.cost_usd ?? 0})`);
    }
    if (day.transport) lines.push(`  Transport: ${day.transport}`);
    if (day.accommodation) lines.push(`  Stay: ${day.accommodation}`);
    if (day.daily_cost_usd != null) lines.push(`  Daily cost: $${day.daily_cost_usd}`);
    if (day.tips && day.tips.length > 0) {
      lines.push(`  💡 ${day.tips[0]}`);
    }
    lines.push('');
  }

  if (itinerary.warnings && itinerary.warnings.length > 0) {
    for (const w of itinerary.warnings) {
      lines.push(`⚠ ${w}`);
    }
  }

  if (itinerary.packing_essentials && itinerary.packing_essentials.length > 0) {
    lines.push(`🎒 Pack: ${itinerary.packing_essentials.join(', ')}`);
  }

  return lines.join('\n');
}

export function formatComparisonText(data: ComparisonData): string {
  const lines: string[] = [];

  for (const plan of data.plans ?? []) {
    const itin = plan.itinerary;
    const cost = itin.estimated_total_cost_usd != null
      ? `$${itin.estimated_total_cost_usd.toLocaleString()}`
      : plan.cost_breakdown?.total != null
        ? `$${plan.cost_breakdown.total.toLocaleString()}`
        : 'N/A';

    lines.push(`=== ${plan.tier.toUpperCase()} — ${cost} ===`);
    lines.push(formatItineraryText(itin));
    if (plan.tradeoffs && plan.tradeoffs.length > 0) {
      lines.push('Tradeoffs:');
      for (const t of plan.tradeoffs) {
        lines.push(`  - ${t}`);
      }
    }
    lines.push('');
  }

  return lines.join('\n');
}

export function buildCopyContent(
  messageContent: string,
  itinerary?: Itinerary | null,
  comparison?: ComparisonData | null,
): string {
  const parts: string[] = [];

  if (itinerary) {
    parts.push(formatItineraryText(itinerary));
  }

  if (comparison) {
    parts.push(formatComparisonText(comparison));
  }

  if (messageContent) {
    parts.push(messageContent);
  }

  return parts.join('\n\n').trim();
}

interface CopyButtonProps {
  content: string;
  label?: string;
  className?: string;
}

export default function CopyButton({ content, label, className }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const t = useTranslations('chat');

  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className={
        className ??
        'p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer'
      }
      aria-label={label ?? t('copy')}
      title={label ?? t('copy')}
    >
      {copied ? (
        <Check className="w-3.5 h-3.5 text-emerald-600" />
      ) : (
        <Copy className="w-3.5 h-3.5" />
      )}
    </button>
  );
}
