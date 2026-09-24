/// <reference types="google.maps" />
'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import useSWR from 'swr';
import { setOptions, importLibrary } from '@googlemaps/js-api-loader';
import { useTranslations } from 'next-intl';
import type { DayPlan, TimeSlot } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import type { Currency } from '@/lib/currency';
import { geocodeLocation, shouldCorrectCoordinates } from '@/lib/geocode';

interface ItineraryMapProps {
  days: DayPlan[];
  destination: string;
  // The itinerary's currency — wins over the app preference when provided.
  currency?: Currency;
  activeDay?: number | null;
  onMarkerClick?: (day: number) => void;
  onDaySelect?: (day: number) => void;
}

const SLOTS = [
  { key: 'morning' as const, labelKey: 'morning' as const, chartNum: 1 },
  { key: 'afternoon' as const, labelKey: 'afternoon' as const, chartNum: 2 },
  { key: 'evening' as const, labelKey: 'evening' as const, chartNum: 3 },
];

const CHART_HEX: Record<number, string> = {
  1: '#b8402e',
  2: '#4d8a62',
  3: '#c29438',
};

// Material "place" teardrop glyph — scaled to roughly the old 28px DOM pin.
const PIN_PATH =
  'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z';

interface MapMarker {
  lat: number;
  lng: number;
  activity: string;
  location: string;
  cost_usd: number;
  duration: string;
  slot: string;
  slotIndex: number;
  day: number;
  approximate?: boolean;
}

export function extractMarkers(day: DayPlan): MapMarker[] {
  const markers: MapMarker[] = [];
  SLOTS.forEach(({ key }, index) => {
    const slot = day[key];
    if (slot && typeof slot.lat === 'number' && typeof slot.lng === 'number') {
      markers.push({
        lat: slot.lat,
        lng: slot.lng,
        activity: slot.activity,
        location: slot.location,
        cost_usd: slot.cost_usd,
        duration: slot.duration,
        slot: key,
        slotIndex: index + 1,
        day: day.day,
        approximate: slot.geo_approx === true,
      });
    }
  });
  return markers;
}

async function geocodeDay(day: DayPlan): Promise<DayPlan> {
  const correctedDay = { ...day };
  const results = await Promise.all(
    SLOTS.map(async ({ key }) => {
      const slot = day[key];
      if (slot?.lat && slot?.lng) {
        const result = await geocodeLocation(`${slot.activity} ${slot.location}`);
        if (result && shouldCorrectCoordinates(slot.lat, slot.lng, result)) {
          return { key, lat: result.lat, lng: result.lng };
        }
      }
      return null;
    })
  );
  for (const result of results) {
    if (result) {
      correctedDay[result.key] = {
        ...correctedDay[result.key],
        lat: result.lat,
        lng: result.lng,
        // Correction upgraded this slot to an exact pin — drop the flag.
        geo_approx: false,
      } as TimeSlot;
    }
  }
  return correctedDay;
}

// Approximate pins render semi-transparent — visibly less certain than exact.
export function markerIcon(slotIndex: number, approximate = false): google.maps.Symbol {
  return {
    path: PIN_PATH,
    fillColor: CHART_HEX[slotIndex] ?? CHART_HEX[1],
    fillOpacity: approximate ? 0.35 : 1,
    strokeColor: '#ffffff',
    strokeWeight: 2,
    scale: 1.5,
    anchor: new google.maps.Point(12, 22),
    labelOrigin: new google.maps.Point(12, 9),
  };
}

export default function ItineraryMap({ days, destination, currency, activeDay, onMarkerClick, onDaySelect }: ItineraryMapProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const infoWindowRef = useRef<google.maps.InfoWindow | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);

  const daysWithCoords = useMemo(
    () => days.filter((d) => extractMarkers(d).length > 0),
    [days]
  );
  const hasAnyCoords = daysWithCoords.length > 0;

  const [mapFailed, setMapFailed] = useState(false);
  // Marker/route/camera updates must re-run once the async API load resolves —
  // without this flag they fire before mapRef is set and pins never appear.
  const [mapReady, setMapReady] = useState(false);

  const [internalSelectedDay, setInternalSelectedDay] = useState(0);
  const isControlled = activeDay !== undefined;
  const selectedDayIndex = isControlled
    ? Math.max(0, daysWithCoords.findIndex((d) => d.day === activeDay))
    : internalSelectedDay;

  const currentDayRaw = daysWithCoords[selectedDayIndex] ?? daysWithCoords[0];

  // Marker signature: an edit/regenerate can swap in different activities
  // under the same day numbers — the SWR key and the marker-update effect
  // must re-fire, not serve the stale cached geocode/camera.
  const daysSig = useMemo(
    () =>
      daysWithCoords
        .map((d) =>
          `${d.day}:${extractMarkers(d)
            .map((m) => `${m.activity}|${m.location}|${m.lat},${m.lng}`)
            .join(';')}`
        )
        .join('|'),
    [daysWithCoords]
  );

  const { data: geocodedDay } = useSWR(
    currentDayRaw ? `geocode-day:${currentDayRaw.day}:${daysSig}` : null,
    () => geocodeDay(currentDayRaw),
    { revalidateOnFocus: false, dedupingInterval: 600000 }
  );

  const currentDay = geocodedDay ?? currentDayRaw;
  const currentMarkers = currentDay ? extractMarkers(currentDay) : [];

  // Load the Maps JS API + create the map once on mount. Without a key we
  // render the link-list fallback — no watermark, no broken tiles.
  useEffect(() => {
    if (!hasAnyCoords || !apiKey || !mapContainerRef.current) return;
    let cancelled = false;

    // Give the loader a fair chance before falling back — a slow connection
    // shouldn't flash the unavailable state.
    const failTimer = setTimeout(() => {
      if (!cancelled) setMapFailed(true);
    }, 10000);

    setOptions({ key: apiKey, v: 'weekly' });
    importLibrary('maps')
      .then(() => {
        if (cancelled || !mapContainerRef.current) return;
        const map = new google.maps.Map(mapContainerRef.current, {
          center:
            currentMarkers.length > 0
              ? { lat: currentMarkers[0].lat, lng: currentMarkers[0].lng }
              : { lat: 0, lng: 0 },
          zoom: 12,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
          clickableIcons: false,
        });
        mapRef.current = map;
        clearTimeout(failTimer);
        setMapFailed(false);
        setMapReady(true);

        // Google Maps doesn't always re-layout when the container is revealed
        // inside a collapsed section/dialog — nudge it on size changes.
        observerRef.current =
          typeof ResizeObserver !== 'undefined'
            ? new ResizeObserver(() => google.maps.event.trigger(map, 'resize'))
            : null;
        observerRef.current?.observe(mapContainerRef.current);
      })
      .catch((err: unknown) => {
        console.error('Google Maps failed to load', err);
        if (!cancelled) setMapFailed(true);
      });

    return () => {
      cancelled = true;
      clearTimeout(failTimer);
      observerRef.current?.disconnect();
      observerRef.current = null;
      markersRef.current.forEach((m) => m.setMap(null));
      markersRef.current = [];
      polylinesRef.current.forEach((p) => p.setMap(null));
      polylinesRef.current = [];
      infoWindowRef.current?.close();
      infoWindowRef.current = null;
      mapRef.current = null;
      setMapReady(false);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAnyCoords]);

  // Update markers, route polyline and camera when the selected day changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || currentMarkers.length === 0) return;

    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];

    const infoWindow = new google.maps.InfoWindow();
    infoWindowRef.current = infoWindow;

    for (const m of currentMarkers) {
      const marker = new google.maps.Marker({
        position: { lat: m.lat, lng: m.lng },
        map,
        icon: markerIcon(m.slotIndex, m.approximate),
        label: { text: String(m.slotIndex), color: '#ffffff', fontSize: '11px', fontWeight: 'bold' },
      });

      marker.addListener('click', () => {
        infoWindow.setContent(`
          <div class="font-sans min-w-[180px] p-1">
            <p class="font-semibold text-sm">${m.activity}</p>
            <p class="text-xs mt-0.5">${t(m.slot)} &middot; ${m.location}</p>
            ${m.approximate ? `<p class="text-[10px] italic mt-0.5">${t('approxLocation')}</p>` : ''}
            <div class="flex items-center gap-3 text-xs mt-1">
              ${m.duration ? `<span>⏱ ${m.duration}</span>` : ''}
              ${m.cost_usd > 0 ? `<span>💰 ${formatCurrency(m.cost_usd, locale, undefined, currency)}</span>` : ''}
            </div>
            <a href="https://www.google.com/maps/search/?api=1&query=${m.lat},${m.lng}" target="_blank" rel="noopener noreferrer" class="text-xs mt-1.5 inline-block">
              ${t('openInMaps')} &rarr;
            </a>
          </div>
        `);
        infoWindow.open({ anchor: marker, map });
        onMarkerClick?.(m.day);
      });

      markersRef.current.push(marker);
    }

    // Dashed route between consecutive slots, each segment colored by the
    // destination slot's color (same scheme as the old MapLibre layer).
    for (let i = 0; i < currentMarkers.length - 1; i++) {
      const from = currentMarkers[i];
      const to = currentMarkers[i + 1];
      polylinesRef.current.push(
        new google.maps.Polyline({
          path: [
            { lat: from.lat, lng: from.lng },
            { lat: to.lat, lng: to.lng },
          ],
          geodesic: true,
          strokeOpacity: 0,
          icons: [
            {
              icon: {
                path: 'M 0,-1 0,1',
                strokeColor: CHART_HEX[to.slotIndex] ?? CHART_HEX[1],
                strokeOpacity: 1,
                scale: 3,
              },
              offset: '0',
              repeat: '14px',
            },
          ],
          map,
        })
      );
    }

    const bounds = new google.maps.LatLngBounds();
    for (const m of currentMarkers) {
      bounds.extend({ lat: m.lat, lng: m.lng });
    }
    map.fitBounds(bounds, 60);
    // Single-point bounds zoom to max street level — cap at city zoom.
    google.maps.event.addListenerOnce(map, 'bounds_changed', () => {
      const zoom = map.getZoom();
      if (zoom !== undefined && zoom > 14) map.setZoom(14);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapReady, currentDay?.day, geocodedDay, destination, daysSig]);

  if (!hasAnyCoords) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 p-4 text-center text-sm text-muted-foreground">
        {t('mapUnavailable')}
      </div>
    );
  }

  const handleTabClick = (index: number, dayNumber: number) => {
    if (onDaySelect) {
      onDaySelect(dayNumber);
    } else {
      setInternalSelectedDay(index);
    }
  };

  return (
    <div className="space-y-3">
      {daysWithCoords.length > 1 && (
      <div className="flex flex-wrap gap-1.5">
        {daysWithCoords.map((d, i) => (
          <button
            key={d.day}
            onClick={() => handleTabClick(i, d.day)}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              i === selectedDayIndex
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {t('dayN', { n: d.day })}
          </button>
        ))}
      </div>
      )}

      <div className="relative">
        <div
          ref={mapContainerRef}
          className="w-full h-[360px] rounded-lg border border-border overflow-hidden"
          aria-label={t('mapForDay', { day: currentDay?.day ?? 1, destination })}
        />
        {(!apiKey || mapFailed) && (
          <div className="absolute inset-0 rounded-lg border border-border bg-muted/95 p-4 space-y-2 overflow-y-auto">
            <p className="text-sm text-muted-foreground">{t('mapUnavailable')}</p>
            <ul className="space-y-1">
              {currentMarkers.map((m) => (
                <li key={m.slot} className="text-xs">
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${m.lat},${m.lng}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:text-primary/80"
                  >
                    {t(m.slot)}: {m.activity} &rarr;
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        {currentMarkers.map((m) => (
          <div key={m.slot} className="flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ background: CHART_HEX[m.slotIndex] ?? CHART_HEX[1] }}
            />
            {t(m.slot)}: {m.activity}
          </div>
        ))}
      </div>
    </div>
  );
}
