import { useState, useEffect, useRef } from 'react';

export function useThrottledValue<T>(value: T, enabled: boolean): T {
  const [throttled, setThrottled] = useState(value);
  const rafRef = useRef<number | null>(null);
  const latestRef = useRef(value);

  latestRef.current = value;

  useEffect(() => {
    if (!enabled) {
      setThrottled(value);
      return;
    }

    if (rafRef.current !== null) return;

    rafRef.current = requestAnimationFrame(() => {
      setThrottled(latestRef.current);
      rafRef.current = null;
    });

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [value, enabled]);

  return enabled ? throttled : value;
}
