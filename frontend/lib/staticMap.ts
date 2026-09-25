import type { DayPlan } from '@/lib/types';

const SLOT_ORDER = ['morning', 'afternoon', 'evening'] as const;

/**
 * Build a Google Static Maps image URL for one itinerary day.
 *
 * Used by the print/export view — the interactive map can't be captured by
 * window.print, but a static PNG prints perfectly. Markers are labeled 1..N
 * in slot order (morning=1, afternoon=2, evening=3) in a single color.
 *
 * Returns null when the day has no slot coordinates.
 */
export function staticDayMapUrl(day: DayPlan, apiKey: string): string | null {
  const points: { lat: number; lng: number }[] = [];
  for (const key of SLOT_ORDER) {
    const slot = day[key];
    if (typeof slot?.lat === 'number' && typeof slot?.lng === 'number') {
      points.push({ lat: slot.lat, lng: slot.lng });
    }
  }
  if (points.length === 0) return null;

  const base = 'https://maps.googleapis.com/maps/api/staticmap';
  const params = new URLSearchParams({ size: '640x200', scale: '2', key: apiKey });
  // One marker can't auto-fit — pin a zoom level; multi-point fits itself.
  if (points.length === 1) params.set('zoom', '14');
  const markerParams = points
    .map((p, i) => `markers=${encodeURIComponent(`size:mid|color:0x6366f1|label:${i + 1}|${p.lat},${p.lng}`)}`)
    .join('&');

  return `${base}?${params.toString()}&${markerParams}`;
}
