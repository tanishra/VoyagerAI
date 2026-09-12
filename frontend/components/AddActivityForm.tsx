'use client';

import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import type { TimeSlot } from '@/lib/types';

interface AddActivityFormProps {
  onAdd: (slot: TimeSlot) => void;
  onCancel: () => void;
}

export default function AddActivityForm({ onAdd, onCancel }: AddActivityFormProps) {
  const t = useTranslations('itinerary');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [cost, setCost] = useState('');
  const [duration, setDuration] = useState('');
  const [error, setError] = useState('');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError(t('activityName'));
      return;
    }
    const slot: TimeSlot = {
      activity: name.trim(),
      location: location.trim(),
      cost_usd: cost ? parseFloat(cost) || 0 : 0,
      duration: duration.trim(),
    };
    onAdd(slot);
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-dashed border-border p-2 space-y-2 bg-muted/20">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Plus className="w-3 h-3" />
          {t('addActivity')}
        </span>
        <button
          type="button"
          onClick={onCancel}
          className="p-0.5 rounded text-muted-foreground/40 hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
          aria-label={t('cancel')}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <input
        type="text"
        value={name}
        onChange={(e) => { setName(e.target.value); setError(''); }}
        placeholder={t('activityName')}
        autoFocus
        className="w-full px-2 py-1.5 text-sm rounded-md border border-border bg-card text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/40 transition-colors"
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
      <input
        type="text"
        value={location}
        onChange={(e) => setLocation(e.target.value)}
        placeholder={t('locationPlaceholder')}
        className="w-full px-2 py-1.5 text-xs rounded-md border border-border bg-card text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/40 transition-colors"
      />
      <div className="flex gap-2">
        <input
          type="number"
          value={cost}
          onChange={(e) => setCost(e.target.value)}
          placeholder={t('estimatedCost')}
          min="0"
          step="0.01"
          className="flex-1 px-2 py-1.5 text-xs rounded-md border border-border bg-card text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/40 transition-colors"
        />
        <input
          type="text"
          value={duration}
          onChange={(e) => setDuration(e.target.value)}
          placeholder={t('durationPlaceholder')}
          className="flex-1 px-2 py-1.5 text-xs rounded-md border border-border bg-card text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/40 transition-colors"
        />
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          className="flex-1 px-2 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer"
        >
          {t('addActivity')}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-2 py-1.5 text-xs rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
        >
          {t('cancel')}
        </button>
      </div>
    </form>
  );
}
