'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MapPin,
  Calendar,
  DollarSign,
  Sparkles,
  Users,
  Utensils,
  Send,
  Globe,
  Compass,
  Gem,
  Wallet,
  Heart,
  User,
  UsersRound,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  Plane,
  Palmtree,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { PlanRequest } from '@/lib/types';

const travelStyles = [
  { value: 'adventure', label: 'Adventure', icon: Compass, desc: 'Hiking, rafting, exploration', gradient: 'from-emerald-500/20 to-teal-500/20', border: 'border-emerald-500/30', selectedBorder: 'border-emerald-400/60', textColor: 'text-emerald-400' },
  { value: 'cultural', label: 'Cultural', icon: Palmtree, desc: 'Museums, history, local life', gradient: 'from-violet-500/20 to-purple-500/20', border: 'border-violet-500/30', selectedBorder: 'border-violet-400/60', textColor: 'text-violet-400' },
  { value: 'luxury', label: 'Luxury', icon: Gem, desc: 'Fine dining, resorts, premium', gradient: 'from-amber-500/20 to-yellow-500/20', border: 'border-amber-500/30', selectedBorder: 'border-amber-400/60', textColor: 'text-amber-400' },
  { value: 'budget', label: 'Budget', icon: Wallet, desc: 'Hostels, street food, savings', gradient: 'from-blue-500/20 to-cyan-500/20', border: 'border-blue-500/30', selectedBorder: 'border-blue-400/60', textColor: 'text-blue-400' },
];

const groupTypes = [
  { value: 'solo', label: 'Solo', emoji: '🧳', icon: User, desc: 'Just me' },
  { value: 'couple', label: 'Couple', emoji: '💑', icon: Heart, desc: 'Two travelers' },
  { value: 'family', label: 'Family', emoji: '👨‍👩‍👧‍👦', icon: UsersRound, desc: '3 or more' },
];

const popularCities = ['Tokyo', 'Paris', 'Bali', 'Rome', 'Bangkok', 'New York', 'Barcelona', 'Dubai'];

const stepLabels = ['Destination', 'Style & Budget', 'Preferences'];

interface TripWizardProps {
  onSubmit: (data: PlanRequest) => void;
  loading: boolean;
}

export default function TripWizard({ onSubmit, loading }: TripWizardProps) {
  const [step, setStep] = useState(0);
  const [formData, setFormData] = useState<PlanRequest>({
    destination: '',
    days: 5,
    budget_usd: 2000,
    travel_style: 'cultural',
    group_type: 'solo',
    dietary: '',
    constraints: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const updateField = <K extends keyof PlanRequest>(key: K, value: PlanRequest[K]) => {
    setFormData(prev => ({ ...prev, [key]: value }));
    if (errors[key]) {
      setErrors(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const validateStep = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};
    if (step === 0) {
      if (!formData.destination.trim()) newErrors.destination = 'Enter a destination';
      if (formData.days < 1 || formData.days > 30) newErrors.days = 'Between 1-30 days';
      if (formData.budget_usd < 50) newErrors.budget_usd = 'Minimum $50';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [step, formData]);

  const handleNext = () => {
    if (validateStep()) setStep(s => Math.min(s + 1, 2));
  };

  const handleBack = () => setStep(s => Math.max(s - 1, 0));

  const handleSubmit = () => {
    if (validateStep()) onSubmit(formData);
  };

  const slideVariants = {
    enter: (dir: number) => ({ x: dir > 0 ? 300 : -300, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir: number) => ({ x: dir > 0 ? -300 : 300, opacity: 0 }),
  };

  const slideDir = step;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-2xl shadow-2xl shadow-sky-500/5">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-sky-500 via-blue-500 to-indigo-500" />

        {/* Progress header */}
        <div className="px-8 pt-8 pb-2">
          <div className="flex items-center justify-between mb-6">
            {stepLabels.map((label, i) => (
              <div key={label} className="flex items-center gap-2 flex-1">
                <div className="flex items-center gap-2">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500 ${
                      i < step
                        ? 'bg-sky-500 text-white'
                        : i === step
                        ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40'
                        : 'bg-white/5 text-white/30 border border-white/10'
                    }`}
                  >
                    {i < step ? <Check className="w-4 h-4" /> : i + 1}
                  </div>
                  <span className={`text-xs font-medium hidden sm:block ${
                    i === step ? 'text-white/90' : 'text-white/30'
                  }`}>
                    {label}
                  </span>
                </div>
                {i < stepLabels.length - 1 && (
                  <div className={`flex-1 h-px mx-3 ${
                    i < step ? 'bg-sky-500/50' : 'bg-white/10'
                  }`} />
                )}
              </div>
            ))}
          </div>

          {/* Progress bar */}
          <div className="h-1 rounded-full bg-white/5 mb-6 overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-sky-500 to-blue-500 rounded-full"
              initial={false}
              animate={{ width: `${((step + 1) / stepLabels.length) * 100}%` }}
              transition={{ duration: 0.4, ease: 'easeInOut' }}
            />
          </div>
        </div>

        <div className="px-8 pb-8">
          <AnimatePresence mode="wait" custom={slideDir}>
            <motion.div
              key={step}
              custom={slideDir}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: 'easeInOut' }}
            >
              {/* Step 0: Destination + Dates */}
              {step === 0 && (
                <div className="space-y-6">
                  <div className="text-center mb-6">
                    <h2 className="text-2xl font-bold text-white mb-1">Where to?</h2>
                    <p className="text-sm text-muted-foreground">Choose your dream destination</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                      <MapPin className="w-4 h-4 text-sky-400" />
                      Destination
                    </label>
                    <Input
                      placeholder="e.g. Tokyo, Japan"
                      value={formData.destination}
                      onChange={e => updateField('destination', e.target.value)}
                      className="bg-white/5 border-white/10 focus:border-sky-500/50 h-12 text-base placeholder:text-white/20"
                      aria-label="Travel destination"
                    />
                    {errors.destination && (
                      <p className="text-xs text-red-400 flex items-center gap-1 mt-1"><AlertCircle className="w-3 h-3" /> {errors.destination}</p>
                    )}
                  </div>

                  {/* Popular destinations */}
                  <div>
                    <p className="text-xs text-muted-foreground mb-2">Popular destinations</p>
                    <div className="flex flex-wrap gap-2">
                      {popularCities.map(city => (
                        <button
                          key={city}
                          type="button"
                          onClick={() => updateField('destination', city)}
                          className={`px-3 py-1.5 text-xs rounded-full border transition-all cursor-pointer ${
                            formData.destination === city
                              ? 'bg-sky-500/20 border-sky-500/40 text-sky-300'
                              : 'border-white/10 text-white/50 hover:border-white/30 hover:text-white/70'
                          }`}
                        >
                          {city}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Days + Budget */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                        <Calendar className="w-4 h-4 text-blue-400" />
                        Days
                      </label>
                      <Input
                        type="number" min={1} max={30}
                        value={formData.days}
                        onChange={e => updateField('days', parseInt(e.target.value) || 1)}
                        className="bg-white/5 border-white/10 focus:border-blue-500/50 h-12 text-base"
                        aria-label="Number of travel days"
                      />
                      {errors.days && <p className="text-xs text-red-400 flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {errors.days}</p>}
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                        <DollarSign className="w-4 h-4 text-emerald-400" />
                        Budget (USD)
                      </label>
                      <Input
                        type="number" min={50}
                        value={formData.budget_usd}
                        onChange={e => updateField('budget_usd', parseInt(e.target.value) || 50)}
                        className="bg-white/5 border-white/10 focus:border-emerald-500/50 h-12 text-base"
                        aria-label="Budget in US dollars"
                      />
                      {errors.budget_usd && <p className="text-xs text-red-400 flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {errors.budget_usd}</p>}
                    </div>
                  </div>

                  {/* Budget quick picks */}
                  <div>
                    <p className="text-xs text-muted-foreground mb-2">Quick budget</p>
                    <div className="flex gap-2">
                      {[500, 1500, 3000, 5000].map(amt => (
                        <button
                          key={amt}
                          type="button"
                          onClick={() => updateField('budget_usd', amt)}
                          className={`flex-1 py-2 text-xs font-medium rounded-lg border transition-all cursor-pointer ${
                            formData.budget_usd === amt
                              ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                              : 'border-white/10 text-white/40 hover:border-white/30'
                          }`}
                        >
                          ${amt}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Step 1: Travel Style + Group */}
              {step === 1 && (
                <div className="space-y-6">
                  <div className="text-center mb-6">
                    <h2 className="text-2xl font-bold text-white mb-1">Your Vibe</h2>
                    <p className="text-sm text-muted-foreground">How do you like to travel?</p>
                  </div>

                  <div className="space-y-3">
                    <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      Travel Style
                    </label>
                    <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Travel style">
                      {travelStyles.map(style => {
                        const sel = formData.travel_style === style.value;
                        return (
                          <button
                            key={style.value}
                            type="button"
                            onClick={() => updateField('travel_style', style.value)}
                            role="radio"
                            aria-checked={sel}
                            className={`relative flex flex-col gap-2 p-4 rounded-xl border transition-all duration-300 cursor-pointer bg-gradient-to-br ${style.gradient} ${
                              sel ? `${style.selectedBorder} ring-2 ring-sky-500/40 shadow-lg shadow-sky-500/10` : `${style.border} opacity-60 hover:opacity-100`
                            }`}
                          >
                            <style.icon className={`w-5 h-5 ${style.textColor}`} />
                            <span className="text-sm font-semibold text-white/90">{style.label}</span>
                            <span className="text-xs text-white/50">{style.desc}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                      <Users className="w-4 h-4 text-cyan-400" />
                      Group Type
                    </label>
                    <div className="flex gap-3" role="radiogroup" aria-label="Group type">
                      {groupTypes.map(group => {
                        const sel = formData.group_type === group.value;
                        return (
                          <button
                            key={group.value}
                            type="button"
                            onClick={() => updateField('group_type', group.value)}
                            role="radio"
                            aria-checked={sel}
                            className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border transition-all cursor-pointer ${
                              sel
                                ? 'bg-white/10 border-cyan-500/50 shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-500/30'
                                : 'bg-white/[0.03] border-white/10 opacity-60 hover:opacity-100 hover:border-white/20'
                            }`}
                          >
                            <span className="text-2xl">{group.emoji}</span>
                            <span className="text-sm font-medium text-white/90">{group.label}</span>
                            <span className="text-xs text-white/50">{group.desc}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* Step 2: Preferences + Review */}
              {step === 2 && (
                <div className="space-y-6">
                  <div className="text-center mb-6">
                    <h2 className="text-2xl font-bold text-white mb-1">Almost there</h2>
                    <p className="text-sm text-muted-foreground">Any special requests?</p>
                  </div>

                  <div className="space-y-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                        <Utensils className="w-4 h-4 text-orange-400" />
                        Dietary Preferences <span className="text-xs text-muted-foreground">(optional)</span>
                      </label>
                      <Input
                        placeholder="e.g. Vegetarian, Halal, Gluten-free"
                        value={formData.dietary}
                        onChange={e => updateField('dietary', e.target.value)}
                        className="bg-white/5 border-white/10 focus:border-orange-500/50 h-12 text-base placeholder:text-white/20"
                        aria-label="Dietary preferences"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                        <AlertCircle className="w-4 h-4 text-yellow-400" />
                        Special Constraints <span className="text-xs text-muted-foreground">(optional)</span>
                      </label>
                      <Textarea
                        placeholder="e.g. Wheelchair accessible, no long walks, avoid heights..."
                        value={formData.constraints}
                        onChange={e => updateField('constraints', e.target.value)}
                        className="bg-white/5 border-white/10 focus:border-yellow-500/50 min-h-[80px] text-base placeholder:text-white/20 resize-none"
                        aria-label="Special constraints"
                      />
                    </div>
                  </div>

                  {/* Trip summary */}
                  <div className="rounded-xl bg-white/[0.04] border border-white/5 p-4 space-y-2">
                    <p className="text-xs font-semibold text-white/50 uppercase tracking-wider">Trip Summary</p>
                    <div className="flex items-center gap-3">
                      <span className="p-2 rounded-lg bg-sky-500/10"><Plane className="w-4 h-4 text-sky-400" /></span>
                      <div>
                        <p className="text-sm font-medium text-white">{formData.destination || 'Not set'}</p>
                        <p className="text-xs text-muted-foreground">
                          {formData.days} days · ${formData.budget_usd} · {formData.travel_style} · {formData.group_type}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {/* Navigation buttons */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-white/5">
            {step > 0 ? (
              <Button
                variant="ghost"
                onClick={handleBack}
                disabled={loading}
                className="text-muted-foreground hover:text-white transition-colors cursor-pointer"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            ) : <div />}

            {step < 2 ? (
              <Button
                onClick={handleNext}
                className="bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 border-0 shadow-lg shadow-sky-500/20 cursor-pointer"
              >
                Next
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={loading}
                className="bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 border-0 shadow-lg shadow-sky-500/20 cursor-pointer disabled:opacity-50"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                      <Globe className="w-4 h-4" />
                    </motion.div>
                    Creating…
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Send className="w-4 h-4" />
                    Generate Itinerary
                  </span>
                )}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
