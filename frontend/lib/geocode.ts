export interface GeocodeResult {
  lat: number;
  lng: number;
  displayName: string;
}

export async function geocodeLocation(query: string): Promise<GeocodeResult | null> {
  try {
    const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`;
    const res = await fetch(url, {
      headers: { 'Accept-Language': 'en' },
    });
    const data = await res.json();
    if (!data || data.length === 0) return null;
    return {
      lat: parseFloat(data[0].lat),
      lng: parseFloat(data[0].lon),
      displayName: data[0].display_name,
    };
  } catch {
    return null;
  }
}

export function shouldCorrectCoordinates(
  originalLat: number,
  originalLng: number,
  geocoded: GeocodeResult,
): boolean {
  const deltaLat = Math.abs(originalLat - geocoded.lat);
  const deltaLng = Math.abs(originalLng - geocoded.lng);
  return deltaLat > 0.01 || deltaLng > 0.01;
}
