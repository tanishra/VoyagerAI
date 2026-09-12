'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import useSWR from 'swr';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useTranslations } from 'next-intl';
import type { DayPlan, TimeSlot } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { geocodeLocation, shouldCorrectCoordinates } from '@/lib/geocode';

interface ItineraryMapProps {
  days: DayPlan[];
  destination: string;
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
}

function extractMarkers(day: DayPlan): MapMarker[] {
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
      } as TimeSlot;
    }
  }
  return correctedDay;
}

function createMarkerElement(slotIndex: number): HTMLElement {
  const el = document.createElement('div');
  el.className = 'flex items-center justify-center cursor-pointer';
  el.style.width = '28px';
  el.style.height = '28px';
  el.style.borderRadius = '50% 50% 50% 0';
  el.style.transform = 'rotate(-45deg)';
  el.style.background = CHART_HEX[slotIndex] ?? CHART_HEX[1];
  el.style.border = '2px solid white';
  el.style.boxShadow = '0 2px 6px rgba(0,0,0,0.2)';
  const span = document.createElement('span');
  span.style.transform = 'rotate(45deg)';
  span.style.fontSize = '11px';
  span.style.fontWeight = 'bold';
  span.style.color = 'white';
  span.style.fontFamily = 'monospace';
  span.textContent = String(slotIndex);
  el.appendChild(span);
  return el;
}

export default function ItineraryMap({ days, destination, activeDay, onMarkerClick, onDaySelect }: ItineraryMapProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  const daysWithCoords = useMemo(
    () => days.filter((d) => extractMarkers(d).length > 0),
    [days]
  );
  const hasAnyCoords = daysWithCoords.length > 0;

  const [internalSelectedDay, setInternalSelectedDay] = useState(0);
  const isControlled = activeDay !== undefined;
  const selectedDayIndex = isControlled
    ? Math.max(0, daysWithCoords.findIndex((d) => d.day === activeDay))
    : internalSelectedDay;

  const currentDayRaw = daysWithCoords[selectedDayIndex] ?? daysWithCoords[0];

  const { data: geocodedDay } = useSWR(
    currentDayRaw ? `geocode-day:${currentDayRaw.day}` : null,
    () => geocodeDay(currentDayRaw),
    { revalidateOnFocus: false, dedupingInterval: 600000 }
  );

  const currentDay = geocodedDay ?? currentDayRaw;
  const currentMarkers = currentDay ? extractMarkers(currentDay) : [];

  // Create map once on mount
  useEffect(() => {
    if (!hasAnyCoords || !mapContainerRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: currentMarkers.length > 0 ? [currentMarkers[0].lng, currentMarkers[0].lat] : [0, 0],
      zoom: 12,
    });

    mapRef.current = map;

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAnyCoords]);

  // Update markers and fly when day changes
  useEffect(() => {
    if (!mapRef.current || currentMarkers.length === 0) return;
    const map = mapRef.current;

    const updateMap = () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      if (map.getLayer('route')) map.removeLayer('route');
      if (map.getSource('route')) map.removeSource('route');

      for (const m of currentMarkers) {
        const el = createMarkerElement(m.slotIndex);

        const popup = new maplibregl.Popup({ offset: 25 }).setHTML(`
          <div class="font-sans min-w-[180px] p-1">
            <p class="font-semibold text-sm text-foreground">${m.activity}</p>
            <p class="text-xs text-muted-foreground mt-0.5">${t(m.slot)} &middot; ${m.location}</p>
            <div class="flex items-center gap-3 text-xs text-muted-foreground mt-1">
              ${m.duration ? `<span>\u23F1 ${m.duration}</span>` : ''}
              ${m.cost_usd > 0 ? `<span>\u{1F4B0} ${formatCurrency(m.cost_usd, locale)}</span>` : ''}
            </div>
            <a href="https://www.google.com/maps/search/?api=1&query=${m.lat},${m.lng}" target="_blank" rel="noopener noreferrer" class="text-xs text-primary hover:text-primary/80 mt-1.5 inline-block">
              ${t('openInMaps')} &rarr;
            </a>
          </div>
        `);

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([m.lng, m.lat])
          .setPopup(popup)
          .addTo(map);

        if (onMarkerClick) {
          el.addEventListener('click', () => onMarkerClick(m.day));
        }

        markersRef.current.push(marker);
      }

      if (currentMarkers.length >= 2) {
        const features = [];
        for (let i = 0; i < currentMarkers.length - 1; i++) {
          const from = currentMarkers[i];
          const to = currentMarkers[i + 1];
          features.push({
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: [[from.lng, from.lat], [to.lng, to.lat]],
            },
            properties: {
              color: CHART_HEX[to.slotIndex] ?? CHART_HEX[1],
            },
          });
        }

        map.addSource('route', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features } as any,
        });
        map.addLayer({
          id: 'route',
          type: 'line',
          source: 'route',
          layout: {
            'line-join': 'round',
            'line-cap': 'round',
          },
          paint: {
            'line-color': ['get', 'color'],
            'line-width': 3,
            'line-dasharray': [2, 1],
          },
        });
      }

      const bounds = new maplibregl.LngLatBounds();
      for (const m of currentMarkers) {
        bounds.extend([m.lng, m.lat]);
      }
      map.fitBounds(bounds, { padding: 60, maxZoom: 14, duration: 1000 });
    };

    if (map.loaded()) {
      updateMap();
    } else {
      map.once('load', updateMap);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDay?.day, geocodedDay]);

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

      <div
        ref={mapContainerRef}
        className="w-full h-[360px] rounded-lg border border-border overflow-hidden"
        aria-label={t('mapForDay', { day: currentDay?.day ?? 1, destination })}
      />

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
