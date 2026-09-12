'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, Save, Loader2, Wallet } from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { useDroppable, useDraggable } from '@dnd-kit/core';
import type { Itinerary, DayPlan, TimeSlot } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { useCurrency } from '@/lib/useCurrency';
import BudgetStatus from './BudgetStatus';
import EditableActivityCard from './EditableActivityCard';
import AddActivityForm from './AddActivityForm';

interface ItineraryEditorProps {
  itinerary: Itinerary;
  threadId: string;
  onClose: () => void;
  onSave: (modifiedItinerary: Itinerary) => void;
}

type SlotKey = 'morning' | 'afternoon' | 'evening';

const SLOTS: SlotKey[] = ['morning', 'afternoon', 'evening'];

interface RemovedActivity {
  dayIndex: number;
  slotKey: SlotKey;
  slot: TimeSlot;
}

interface DragItemData {
  dayIndex: number;
  slotKey: SlotKey;
}

function deepCloneItinerary(itin: Itinerary): Itinerary {
  return JSON.parse(JSON.stringify(itin));
}

function recalcDayCost(day: DayPlan): number {
  return (day.morning?.cost_usd ?? 0) + (day.afternoon?.cost_usd ?? 0) + (day.evening?.cost_usd ?? 0);
}

function recalcTotalCost(days: DayPlan[]): number {
  return days.reduce((sum, day) => sum + recalcDayCost(day), 0);
}

function DraggableActivity({
  slot,
  slotKey,
  dayIndex,
  totalDays,
  onRemove,
  onMoveUp,
  onMoveDown,
  onMoveLeft,
  onMoveRight,
  isCustom,
}: {
  slot: TimeSlot;
  slotKey: SlotKey;
  dayIndex: number;
  totalDays: number;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onMoveLeft: () => void;
  onMoveRight: () => void;
  isCustom: boolean;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `drag-${dayIndex}-${slotKey}`,
    data: { dayIndex, slotKey } as DragItemData,
  });

  const slotIndex = SLOTS.indexOf(slotKey);
  const canMoveUp = slotIndex > 0;
  const canMoveDown = slotIndex < SLOTS.length - 1;
  const canMoveLeft = dayIndex > 0;
  const canMoveRight = dayIndex < totalDays - 1;

  return (
    <div ref={setNodeRef} {...attributes} {...listeners}>
      <EditableActivityCard
        slot={slot}
        slotKey={slotKey}
        onRemove={onRemove}
        onMoveUp={canMoveUp ? onMoveUp : undefined}
        onMoveDown={canMoveDown ? onMoveDown : undefined}
        onMoveLeft={canMoveLeft ? onMoveLeft : undefined}
        onMoveRight={canMoveRight ? onMoveRight : undefined}
        canMoveUp={canMoveUp}
        canMoveDown={canMoveDown}
        canMoveLeft={canMoveLeft}
        canMoveRight={canMoveRight}
        isCustom={isCustom}
        isDragging={isDragging}
      />
    </div>
  );
}

function DroppableSlot({
  dayIndex,
  slotKey,
  children,
}: {
  dayIndex: number;
  slotKey: SlotKey;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `drop-${dayIndex}-${slotKey}`,
    data: { dayIndex, slotKey },
  });

  return (
    <div
      ref={setNodeRef}
      className={`min-h-[80px] rounded-lg transition-colors ${isOver ? 'bg-primary/10 ring-2 ring-primary/30' : ''}`}
    >
      {children}
    </div>
  );
}

export default function ItineraryEditor({ itinerary, threadId: _threadId, onClose, onSave }: ItineraryEditorProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const [currency] = useCurrency();
  const [editedItinerary, setEditedItinerary] = useState<Itinerary>(() => deepCloneItinerary(itinerary));
  const [, setRemovedActivities] = useState<RemovedActivity[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [showAddForm, setShowAddForm] = useState<number | null>(null);
  const [toast, setToast] = useState<{ message: string; undo?: () => void } | null>(null);
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
  const [customSlots, setCustomSlots] = useState<Set<string>>(new Set());
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  const days = editedItinerary.days ?? [];
  const totalCost = recalcTotalCost(days);
  const hasChanges = JSON.stringify(editedItinerary) !== JSON.stringify(itinerary);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSaving) {
        if (showDiscardConfirm) {
          setShowDiscardConfirm(false);
        } else {
          onClose();
        }
      }
    };
    document.addEventListener('keydown', handleEscape);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [onClose, isSaving, showDiscardConfirm]);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  const updateDay = useCallback((dayIndex: number, updater: (day: DayPlan) => DayPlan) => {
    setEditedItinerary((prev) => {
      const newDays = [...prev.days];
      newDays[dayIndex] = updater(newDays[dayIndex]);
      newDays[dayIndex] = { ...newDays[dayIndex], daily_cost_usd: recalcDayCost(newDays[dayIndex]) };
      return { ...prev, days: newDays, estimated_total_cost_usd: recalcTotalCost(newDays) };
    });
  }, []);

  const handleRemove = useCallback((dayIndex: number, slotKey: SlotKey) => {
    const slot = days[dayIndex][slotKey];
    if (!slot) return;
    const removed: RemovedActivity = { dayIndex, slotKey, slot };
    setRemovedActivities((prev) => [...prev.slice(-9), removed]);
    updateDay(dayIndex, (day) => ({ ...day, [slotKey]: { activity: '', location: '', cost_usd: 0, duration: '' } }));
    setToast({
      message: t('removed', { name: slot.activity }),
      undo: () => {
        updateDay(dayIndex, (day) => ({ ...day, [slotKey]: slot }));
        setRemovedActivities((prev) => prev.filter((r) => r !== removed));
        setToast(null);
      },
    });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(null), 5000);
  }, [days, updateDay, t]);

  const handleAddActivity = useCallback((dayIndex: number, slot: TimeSlot) => {
    const day = days[dayIndex];
    const emptySlot = SLOTS.find((s) => !day[s] || !day[s].activity);
    const targetSlot = emptySlot ?? 'morning';
    updateDay(dayIndex, (d) => ({ ...d, [targetSlot]: slot }));
    setCustomSlots((prev) => new Set(prev).add(`${dayIndex}-${targetSlot}`));
    setShowAddForm(null);
  }, [days, updateDay]);

  const swapSlots = useCallback((dayIndex: number, slotA: SlotKey, slotB: SlotKey) => {
    updateDay(dayIndex, (day) => {
      const temp = day[slotA];
      return { ...day, [slotA]: day[slotB], [slotB]: temp };
    });
  }, [updateDay]);

  const moveBetweenDays = useCallback((fromDay: number, fromSlot: SlotKey, toDay: number, toSlot: SlotKey) => {
    setEditedItinerary((prev) => {
      const newDays = [...prev.days];
      const fromSlotData = newDays[fromDay][fromSlot];
      const toSlotData = newDays[toDay][toSlot];
      newDays[fromDay] = { ...newDays[fromDay], [fromSlot]: toSlotData };
      newDays[toDay] = { ...newDays[toDay], [toSlot]: fromSlotData };
      newDays[fromDay] = { ...newDays[fromDay], daily_cost_usd: recalcDayCost(newDays[fromDay]) };
      newDays[toDay] = { ...newDays[toDay], daily_cost_usd: recalcDayCost(newDays[toDay]) };
      return { ...prev, days: newDays, estimated_total_cost_usd: recalcTotalCost(newDays) };
    });
  }, []);

  const handleMoveUp = useCallback((dayIndex: number, slotKey: SlotKey) => {
    const idx = SLOTS.indexOf(slotKey);
    if (idx > 0) swapSlots(dayIndex, slotKey, SLOTS[idx - 1]);
  }, [swapSlots]);

  const handleMoveDown = useCallback((dayIndex: number, slotKey: SlotKey) => {
    const idx = SLOTS.indexOf(slotKey);
    if (idx < SLOTS.length - 1) swapSlots(dayIndex, slotKey, SLOTS[idx + 1]);
  }, [swapSlots]);

  const handleMoveLeft = useCallback((dayIndex: number, slotKey: SlotKey) => {
    if (dayIndex > 0) moveBetweenDays(dayIndex, slotKey, dayIndex - 1, slotKey);
  }, [moveBetweenDays]);

  const handleMoveRight = useCallback((dayIndex: number, slotKey: SlotKey) => {
    if (dayIndex < days.length - 1) moveBetweenDays(dayIndex, slotKey, dayIndex + 1, slotKey);
  }, [days.length, moveBetweenDays]);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;
    const fromData = active.data.current as DragItemData;
    const toData = over.data.current as DragItemData;
    if (!fromData || !toData) return;
    if (fromData.dayIndex === toData.dayIndex && fromData.slotKey === toData.slotKey) return;

    if (fromData.dayIndex === toData.dayIndex) {
      swapSlots(fromData.dayIndex, fromData.slotKey, toData.slotKey);
    } else {
      moveBetweenDays(fromData.dayIndex, fromData.slotKey, toData.dayIndex, toData.slotKey);
    }
  }, [swapSlots, moveBetweenDays]);

  const handleSave = useCallback(() => {
    setIsSaving(true);
    onSave(editedItinerary);
  }, [editedItinerary, onSave]);

  const handleDiscard = useCallback(() => {
    if (hasChanges) {
      setShowDiscardConfirm(true);
    } else {
      onClose();
    }
  }, [hasChanges, onClose]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget && !isSaving) {
      handleDiscard();
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-0 md:p-4"
        onClick={handleBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label={t('editItinerary')}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.2 }}
          className="w-full h-full md:w-auto md:max-w-5xl md:max-h-[90vh] md:rounded-xl bg-card border border-border shadow-lg flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <div className="flex items-center gap-3">
              <h2 className="font-semibold text-foreground text-base">{t('editItinerary')}</h2>
              <span className="text-sm text-muted-foreground">{editedItinerary.destination}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-primary">
                  {formatCurrency(totalCost, locale, undefined, currency)}
                </span>
                <BudgetStatus
                  status={editedItinerary.budget_status}
                  totalCost={totalCost}
                  currency={currency}
                />
              </div>
              <button
                onClick={handleDiscard}
                disabled={isSaving}
                className="px-3 py-1.5 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer disabled:opacity-50"
              >
                {t('discardChanges')}
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving || !hasChanges}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {t('validating')}
                  </>
                ) : (
                  <>
                    <Save className="w-3.5 h-3.5" />
                    {t('saveChanges')}
                  </>
                )}
              </button>
              <button
                onClick={() => !isSaving && onClose()}
                disabled={isSaving}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer disabled:opacity-50"
                aria-label={t('close')}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Board */}
          <div className="flex-1 overflow-x-auto overflow-y-hidden">
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <div className="flex gap-3 p-4 h-full min-w-max">
                {days.map((day, dayIndex) => (
                  <div
                    key={dayIndex}
                    className="w-72 shrink-0 flex flex-col rounded-lg bg-muted/20 border border-border"
                  >
                    {/* Day header */}
                    <div className="px-3 py-2 border-b border-border">
                      <p className="font-medium text-foreground text-sm">
                        {t('dayN', { n: day.day })}
                      </p>
                      {day.theme && (
                        <p className="text-xs text-muted-foreground truncate">{day.theme}</p>
                      )}
                    </div>

                    {/* Slots */}
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                      {SLOTS.map((slotKey) => {
                        const slot = day[slotKey];
                        const hasActivity = slot && slot.activity;
                        const isCustom = customSlots.has(`${dayIndex}-${slotKey}`);
                        return (
                          <DroppableSlot key={slotKey} dayIndex={dayIndex} slotKey={slotKey}>
                            {hasActivity ? (
                              <DraggableActivity
                                slot={slot}
                                slotKey={slotKey}
                                dayIndex={dayIndex}
                                totalDays={days.length}
                                onRemove={() => handleRemove(dayIndex, slotKey)}
                                onMoveUp={() => handleMoveUp(dayIndex, slotKey)}
                                onMoveDown={() => handleMoveDown(dayIndex, slotKey)}
                                onMoveLeft={() => handleMoveLeft(dayIndex, slotKey)}
                                onMoveRight={() => handleMoveRight(dayIndex, slotKey)}
                                isCustom={isCustom}
                              />
                            ) : (
                              <div className="min-h-[80px] rounded-lg border border-dashed border-border/50 flex items-center justify-center text-xs text-muted-foreground/40">
                                {t('dropHere')}
                              </div>
                            )}
                          </DroppableSlot>
                        );
                      })}

                      {/* Add activity form or button */}
                      {showAddForm === dayIndex ? (
                        <AddActivityForm
                          onAdd={(slot) => handleAddActivity(dayIndex, slot)}
                          onCancel={() => setShowAddForm(null)}
                        />
                      ) : (
                        <button
                          onClick={() => setShowAddForm(dayIndex)}
                          className="w-full flex items-center justify-center gap-1 py-2 rounded-lg border border-dashed border-border text-xs text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors cursor-pointer"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          {t('addActivity')}
                        </button>
                      )}
                    </div>

                    {/* Daily cost footer */}
                    <div className="px-3 py-2 border-t border-border flex items-center justify-between">
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Wallet className="w-3 h-3" />
                        {t('dailyCost')}
                      </span>
                      <span className="text-xs font-semibold text-foreground tabular-nums">
                        {formatCurrency(recalcDayCost(day), locale, undefined, currency)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </DndContext>
          </div>

          {/* Toast */}
          <AnimatePresence>
            {toast && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                className="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-card border border-border shadow-lg flex items-center gap-3"
              >
                <span className="text-sm text-foreground">{toast.message}</span>
                {toast.undo && (
                  <button
                    onClick={toast.undo}
                    className="text-xs font-medium text-primary hover:text-primary/80 cursor-pointer"
                  >
                    {t('undo')}
                  </button>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Discard confirmation */}
          <AnimatePresence>
            {showDiscardConfirm && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 z-10 flex items-center justify-center bg-black/40"
                onClick={(e) => e.target === e.currentTarget && setShowDiscardConfirm(false)}
              >
                <div className="bg-card border border-border rounded-xl shadow-lg p-4 max-w-sm w-full mx-4">
                  <p className="text-sm text-foreground mb-3">{t('unsavedChanges')}</p>
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setShowDiscardConfirm(false)}
                      className="px-3 py-1.5 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                    >
                      {t('cancel')}
                    </button>
                    <button
                      onClick={() => { setShowDiscardConfirm(false); onClose(); }}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors cursor-pointer"
                    >
                      {t('discardChanges')}
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
