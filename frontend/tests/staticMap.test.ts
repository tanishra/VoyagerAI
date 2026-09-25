import { describe, it, expect } from 'vitest';
import { staticDayMapUrl } from '@/lib/staticMap';
import type { DayPlan } from '@/lib/types';

const bare = { activity: 'X', location: 'L', cost_usd: 0, duration: '1h' } as const;

const day = (overrides?: Partial<DayPlan>): DayPlan => ({
  day: 1,
  theme: 'T',
  morning: { activity: 'A', location: 'L', cost_usd: 0, duration: '1h', lat: 35.68, lng: 139.69 },
  afternoon: { activity: 'B', location: 'L', cost_usd: 0, duration: '1h', lat: 35.66, lng: 139.7 },
  evening: { activity: 'C', location: 'L', cost_usd: 0, duration: '1h', lat: 35.67, lng: 139.71 },
  transport: 'T',
  accommodation: 'H',
  daily_cost_usd: 10,
  tips: [],
  ...overrides,
});

describe('staticDayMapUrl', () => {
  it('builds a URL with one labeled marker per coordinated slot', () => {
    const url = staticDayMapUrl(day(), 'k')!;
    expect(url).toContain('maps.googleapis.com/maps/api/staticmap');
    expect(url).toContain('size=640x200');
    expect(url).toContain('key=k');
    expect(url.match(/markers=/g)).toHaveLength(3);
    expect(url).toContain('label%3A1');
    expect(url).toContain('label%3A3');
  });

  it('pins a zoom level for a single point', () => {
    const url = staticDayMapUrl(
      day({ afternoon: { ...bare }, evening: { ...bare } }),
      'k'
    )!;
    expect(url).toContain('zoom=14');
    expect(url.match(/markers=/g)).toHaveLength(1);
  });

  it('skips slots without coordinates', () => {
    const url = staticDayMapUrl(day({ evening: { ...bare } }), 'k')!;
    expect(url.match(/markers=/g)).toHaveLength(2);
    expect(url).not.toContain('zoom=14');
  });

  it('returns null when the day has no coordinates', () => {
    expect(
      staticDayMapUrl(
        day({
          morning: { ...bare },
          afternoon: { ...bare },
          evening: { ...bare },
        }),
        'k'
      )
    ).toBeNull();
  });
});
