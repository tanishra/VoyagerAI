'use client';

import { useState, useCallback, useEffect } from 'react';
import { useLocale } from '@/lib/useLocale';
import {
  getEffectiveCurrency,
  setStoredCurrency,
  type Currency,
} from '@/lib/currency';

export function useCurrency(): [Currency, (currency: Currency) => void] {
  const locale = useLocale();
  const [currency, setCurrencyState] = useState<Currency>(() => getEffectiveCurrency(locale));

  useEffect(() => {
    setCurrencyState(getEffectiveCurrency(locale));
  }, [locale]);

  const setCurrency = useCallback((next: Currency) => {
    setStoredCurrency(next);
    setCurrencyState(next);
  }, []);

  return [currency, setCurrency];
}
