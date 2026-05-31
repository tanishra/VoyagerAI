'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MapPin,
  Calendar,
  DollarSign,
  Users,
  Utensils,
  Plane,
  Compass,
  Gem,
  Wallet,
  Heart,
  User,
  UsersRound,
  Send,
  Sparkles,
  Globe,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import type { PlanRequest } from '@/lib/types';

const travelStyles = [
  { value: 'adventure', label: 'Adventure', emoji: '🏔️', icon: Compass, color: 'from-emerald-500/20 to-teal-500/20 border-emerald-500/30 hover:border-emerald-400/60' },
  { value: 'cultural', label: 'Cultural', emoji: '🏛️', icon: Globe, color: 'from-violet-500/20 to-purple-500/20 border-violet-500/30 hover:border-violet-400/60' },
  { value: 'luxury', label: 'Luxury', emoji: '💎', icon: Gem, color: 'from-amber-500/20 to-yellow-500/20 border-amber-500/30 hover:border-amber-400/60' },
  { value: 'budget', label: 'Budget', emoji: '💰', icon: Wallet, color: 'from-blue-500/20 to-cyan-500/20 border-blue-500/30 hover:border-blue-400/60' },
];

const groupTypes = [
  { value: 'solo', label: 'Solo', emoji: '🧳', icon: User },
  { value: 'couple', label: 'Couple', emoji: '💑', icon: Heart },
  { value: 'family', label: 'Family', emoji: '👨‍👩‍👧‍👦', icon: UsersRound },
];

interface PlanFormProps {
  onSubmit: (data: PlanRequest) => void;
  loading: boolean;
}

export default function PlanForm({ onSubmit, loading }: PlanFormProps) {
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

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.destination.trim()) newErrors.destination = 'Please enter a destination';
    if (formData.days < 1 || formData.days > 30) newErrors.days = 'Days must be between 1 and 30';
    if (formData.budget_usd < 50) newErrors.budget_usd = 'Budget must be at least $50';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) {
      onSubmit(formData);
    }
  };

  const updateField = <K extends keyof PlanRequest>(key: K, value: PlanRequest[K]) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className="w-full max-w-2xl mx-auto"
    >
      <Card className="relative overflow-hidden border-white/10 bg-white/[0.03] backdrop-blur-2xl shadow-2xl shadow-purple-500/5">
        {/* Gradient accent top bar */}
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-purple-500 via-blue-500 to-cyan-500" />

        <CardContent className="p-8 pt-10">
          <form onSubmit={handleSubmit} className="space-y-8" id="plan-form">
            {/* Header */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-center space-y-2"
            >
              <div className="flex items-center justify-center gap-2 mb-4">
                <div className="p-3 rounded-2xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-purple-500/20">
                  <Plane className="w-6 h-6 text-purple-400" />
                </div>
              </div>
              <h2 className="text-2xl font-bold bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">
                Plan Your Dream Trip
              </h2>
              <p className="text-sm text-muted-foreground">
                Let AI craft the perfect itinerary for you
              </p>
            </motion.div>

            {/* Destination */}
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15 }}
              className="space-y-2"
            >
              <label htmlFor="destination" className="text-sm font-medium flex items-center gap-2 text-white/80">
                <MapPin className="w-4 h-4 text-purple-400" />
                Destination
              </label>
              <Input
                id="destination"
                placeholder="e.g. Tokyo, Japan"
                value={formData.destination}
                onChange={(e) => updateField('destination', e.target.value)}
                className="bg-white/[0.05] border-white/10 focus:border-purple-500/50 h-12 text-base placeholder:text-white/20"
                aria-label="Travel destination"
              />
              <AnimatePresence>
                {errors.destination && (
                  <motion.p initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} className="text-xs text-red-400 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" /> {errors.destination}
                  </motion.p>
                )}
              </AnimatePresence>
            </motion.div>

            {/* Days & Budget row */}
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="grid grid-cols-2 gap-4"
            >
              <div className="space-y-2">
                <label htmlFor="days" className="text-sm font-medium flex items-center gap-2 text-white/80">
                  <Calendar className="w-4 h-4 text-blue-400" />
                  Days
                </label>
                <Input
                  id="days"
                  type="number"
                  min={1}
                  max={30}
                  value={formData.days}
                  onChange={(e) => updateField('days', parseInt(e.target.value) || 1)}
                  className="bg-white/[0.05] border-white/10 focus:border-blue-500/50 h-12 text-base"
                  aria-label="Number of travel days"
                />
                <AnimatePresence>
                  {errors.days && (
                    <motion.p initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} className="text-xs text-red-400 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> {errors.days}
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
              <div className="space-y-2">
                <label htmlFor="budget" className="text-sm font-medium flex items-center gap-2 text-white/80">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                  Budget (USD)
                </label>
                <Input
                  id="budget"
                  type="number"
                  min={50}
                  value={formData.budget_usd}
                  onChange={(e) => updateField('budget_usd', parseInt(e.target.value) || 50)}
                  className="bg-white/[0.05] border-white/10 focus:border-emerald-500/50 h-12 text-base"
                  aria-label="Budget in US dollars"
                />
                <AnimatePresence>
                  {errors.budget_usd && (
                    <motion.p initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} className="text-xs text-red-400 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> {errors.budget_usd}
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>

            {/* Travel Style */}
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.25 }}
              className="space-y-3"
            >
              <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                <Sparkles className="w-4 h-4 text-amber-400" />
                Travel Style
              </label>
              <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Travel style selection">
                {travelStyles.map((style) => {
                  const isSelected = formData.travel_style === style.value;
                  return (
                    <motion.button
                      key={style.value}
                      type="button"
                      id={`style-${style.value}`}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => updateField('travel_style', style.value)}
                      role="radio"
                      aria-checked={isSelected}
                      className={`relative flex items-center gap-3 p-4 rounded-xl border transition-all duration-300 cursor-pointer bg-gradient-to-br ${style.color} ${
                        isSelected
                          ? 'ring-2 ring-purple-500/50 shadow-lg shadow-purple-500/10'
                          : 'opacity-60 hover:opacity-100'
                      }`}
                    >
                      <span className="text-xl">{style.emoji}</span>
                      <span className="text-sm font-medium text-white/90">{style.label}</span>
                      {isSelected && (
                        <motion.div
                          layoutId="style-indicator"
                          className="absolute top-2 right-2 w-2 h-2 rounded-full bg-purple-400"
                        />
                      )}
                    </motion.button>
                  );
                })}
              </div>
            </motion.div>

            {/* Group Type */}
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="space-y-3"
            >
              <label className="text-sm font-medium flex items-center gap-2 text-white/80">
                <Users className="w-4 h-4 text-cyan-400" />
                Group Type
              </label>
              <div className="flex gap-3" role="radiogroup" aria-label="Group type selection">
                {groupTypes.map((group) => {
                  const isSelected = formData.group_type === group.value;
                  return (
                    <motion.button
                      key={group.value}
                      type="button"
                      id={`group-${group.value}`}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => updateField('group_type', group.value)}
                      role="radio"
                      aria-checked={isSelected}
                      className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border transition-all duration-300 cursor-pointer ${
                        isSelected
                          ? 'bg-white/10 border-cyan-500/50 shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-500/30'
                          : 'bg-white/[0.03] border-white/10 opacity-60 hover:opacity-100 hover:border-white/20'
                      }`}
                    >
                      <span className="text-xl">{group.emoji}</span>
                      <span className="text-xs font-medium text-white/80">{group.label}</span>
                    </motion.button>
                  );
                })}
              </div>
            </motion.div>

            {/* Dietary & Constraints */}
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.35 }}
              className="space-y-4"
            >
              <div className="space-y-2">
                <label htmlFor="dietary" className="text-sm font-medium flex items-center gap-2 text-white/80">
                  <Utensils className="w-4 h-4 text-orange-400" />
                  Dietary Preferences
                  <span className="text-xs text-muted-foreground">(optional)</span>
                </label>
                <Input
                  id="dietary"
                  placeholder="e.g. Vegetarian, Halal, Gluten-free"
                  value={formData.dietary}
                  onChange={(e) => updateField('dietary', e.target.value)}
                  className="bg-white/[0.05] border-white/10 focus:border-orange-500/50 h-12 text-base placeholder:text-white/20"
                  aria-label="Dietary preferences"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="constraints" className="text-sm font-medium flex items-center gap-2 text-white/80">
                  <AlertCircle className="w-4 h-4 text-yellow-400" />
                  Special Constraints
                  <span className="text-xs text-muted-foreground">(optional)</span>
                </label>
                <Textarea
                  id="constraints"
                  placeholder="e.g. Wheelchair accessible, no long walks, avoid heights..."
                  value={formData.constraints}
                  onChange={(e) => updateField('constraints', e.target.value)}
                  className="bg-white/[0.05] border-white/10 focus:border-yellow-500/50 min-h-[80px] text-base placeholder:text-white/20 resize-none"
                  aria-label="Special constraints or requirements"
                />
              </div>
            </motion.div>

            {/* Submit */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              <Button
                type="submit"
                id="submit-plan"
                disabled={loading}
                className="w-full h-14 text-base font-semibold bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 border-0 shadow-xl shadow-purple-500/20 transition-all duration-300 cursor-pointer disabled:opacity-50"
              >
                {loading ? (
                  <motion.div
                    className="flex items-center gap-3"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                    >
                      <Globe className="w-5 h-5" />
                    </motion.div>
                    <span>Crafting your itinerary…</span>
                  </motion.div>
                ) : (
                  <span className="flex items-center gap-2">
                    <Send className="w-5 h-5" />
                    Generate Itinerary
                  </span>
                )}
              </Button>
            </motion.div>
          </form>
        </CardContent>
      </Card>
    </motion.div>
  );
}
