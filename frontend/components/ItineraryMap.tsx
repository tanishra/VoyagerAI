'use client';

import { useState, useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useTranslations } from 'next-intl';
import type { DayPlan } from '@/lib/types';

interface ItineraryMapProps {
  days: DayPlan[];
  destination: string;
}

const SLOT_KEYS: Record<string, string> = {
  morning: 'morning',
  afternoon: 'afternoon',
  evening: 'evening',
};

const SLOT_COLORS: Record<string, string> = {
  morning: '#f59e0b',
  afternoon: '#3b82f6',
  evening: '#8b5cf6',
};

interface MapMarker {
  lat: number;
  lng: number;
  activity: string;
  location: string;
  cost_usd: number;
  slot: string;
  day: number;
}

function extractMarkers(day: DayPlan): MapMarker[] {
  const markers: MapMarker[] = [];
  for (const slotKey of ['morning', 'afternoon', 'evening'] as const) {
    const slot = day[slotKey];
    if (slot && typeof slot.lat === 'number' && typeof slot.lng === 'number') {
      markers.push({
        lat: slot.lat,
        lng: slot.lng,
        activity: slot.activity,
        location: slot.location,
        cost_usd: slot.cost_usd,
        slot: slotKey,
        day: day.day,
      });
    }
  }
  return markers;
}

export default function ItineraryMap({ days, destination }: ItineraryMapProps) {
  const t = useTranslations('itinerary');
  const [selectedDay, setSelectedDay] = useState(0);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  const daysWithCoords = days.filter((d) => extractMarkers(d).length > 0);
  const hasAnyCoords = daysWithCoords.length > 0;

  useEffect(() => {
    if (!hasAnyCoords || !mapContainerRef.current) return;

    const day = daysWithCoords[selectedDay] ?? daysWithCoords[0];
    const markers = extractMarkers(day);

    if (markers.length === 0) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          'raster-tiles': {
            type: 'raster',
            tiles: [
              'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
            ],
            tileSize: 256,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
          },
        },
        layers: [
          {
            id: 'background',
            type: 'raster',
            source: 'raster-tiles',
            minzoom: 0,
            maxzoom: 20,
          },
        ],
      },
      center: [markers[0].lng, markers[0].lat],
      zoom: 12,
    });

    mapRef.current = map;

    map.on('load', () => {
      // Add route polyline if 2+ markers
      if (markers.length >= 2) {
        const coords = markers.map((m) => [m.lng, m.lat]);
        map.addSource('route', {
          type: 'geojson',
          data: {
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: coords,
            },
            properties: {},
          },
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
            'line-color': '#6366f1',
            'line-width': 3,
            'line-dasharray': [2, 1],
          },
        });
      }

      // Fit bounds to all markers
      const bounds = new maplibregl.LngLatBounds();
      for (const m of markers) {
        bounds.extend([m.lng, m.lat]);
      }
      map.fitBounds(bounds, { padding: 60, maxZoom: 14 });
    });

    // Add markers
    for (const m of markers) {
      const el = document.createElement('div');
      el.style.cssText = `
        width: 24px; height: 24px; border-radius: 50%;
        background: ${SLOT_COLORS[m.slot] ?? '#6366f1'};
        border: 2px solid white; cursor: pointer;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        display: flex; align-items: center; justify-content: center;
        font-size: 11px; font-weight: bold; color: white;
      `;
      const slotIndex = ['morning', 'afternoon', 'evening'].indexOf(m.slot) + 1;
      el.textContent = String(slotIndex);

      const popup = new maplibregl.Popup({ offset: 25 }).setHTML(`
        <div style="font-family: sans-serif; min-width: 160px;">
          <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">${m.activity}</div>
          <div style="font-size: 11px; color: #666; margin-bottom: 4px;">${t(SLOT_KEYS[m.slot] ?? 'morning')} &middot; ${m.location}</div>
          <div style="font-size: 12px; margin-bottom: 6px;">$${m.cost_usd}</div>
          <a href="https://www.google.com/maps/search/?api=1&query=${m.lat},${m.lng}" target="_blank" rel="noopener noreferrer" style="font-size: 11px; color: #3b82f6; text-decoration: none;">${t('openInMaps')} &rarr;</a>
        </div>
      `);

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([m.lng, m.lat])
        .setPopup(popup)
        .addTo(map);
      markersRef.current.push(marker);
    }

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, [selectedDay, hasAnyCoords, daysWithCoords]);

  if (!hasAnyCoords) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 p-4 text-center text-sm text-muted-foreground">
        {t('mapUnavailable')}
      </div>
    );
  }

  const currentDay = daysWithCoords[selectedDay] ?? daysWithCoords[0];
  const currentMarkers = extractMarkers(currentDay);

  return (
    <div className="space-y-3">
      {/* Day selector tabs */}
      <div className="flex flex-wrap gap-1.5">
        {daysWithCoords.map((d, i) => (
          <button
            key={d.day}
            onClick={() => setSelectedDay(i)}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
              i === selectedDay
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {t('dayN', { n: d.day })}
          </button>
        ))}
      </div>

      {/* Map container */}
      <div
        ref={mapContainerRef}
        className="w-full h-[360px] rounded-lg border border-border overflow-hidden"
        aria-label={t('mapForDay', { day: currentDay.day, destination })}
      />

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        {currentMarkers.map((m) => (
          <div key={m.slot} className="flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ background: SLOT_COLORS[m.slot] ?? '#6366f1' }}
            />
            {t(SLOT_KEYS[m.slot] ?? 'morning')}: {m.activity}
          </div>
        ))}
      </div>
    </div>
  );
}
