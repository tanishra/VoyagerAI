import type { Itinerary } from './types';

const ITINERARY_KEY = 'lastItinerary';
const TTL = 60 * 60 * 1000;

interface StoredItinerary {
  data: Itinerary;
  timestamp: number;
}

export function saveItinerary(itinerary: Itinerary): void {
  try {
    const payload: StoredItinerary = { data: itinerary, timestamp: Date.now() };
    localStorage.setItem(ITINERARY_KEY, JSON.stringify(payload));
  } catch {
    /* quota exceeded or private mode — ignore */
  }
}

export function loadItinerary(): Itinerary | null {
  try {
    const raw = localStorage.getItem(ITINERARY_KEY);
    if (!raw) return null;
    const stored: StoredItinerary = JSON.parse(raw);
    if (Date.now() - stored.timestamp > TTL) {
      localStorage.removeItem(ITINERARY_KEY);
      return null;
    }
    return stored.data;
  } catch {
    return null;
  }
}

export function clearItinerary(): void {
  try {
    localStorage.removeItem(ITINERARY_KEY);
  } catch {
    /* ignore */
  }
}
