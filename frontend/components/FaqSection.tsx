'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Search } from 'lucide-react';

interface FaqItem {
  q: string;
  a: string;
}

const faqs: FaqItem[] = [
  {
    q: 'How does Gemini generate my itinerary?',
    a: 'Tell us your destination, budget, travel style, and group size. Gemini creates a complete day-by-day plan with activities, transport, accommodation, and costs — all optimized for your preferences.',
  },
  {
    q: 'Is it really free?',
    a: 'Yes! The travel planner is completely free to use. There are no hidden costs, subscriptions, or premium tiers.',
  },
  {
    q: 'Can I customize the itinerary after it\'s generated?',
    a: 'Absolutely. If a specific day doesn\'t match your expectations, you can use the "Replan This Day" feature to ask for changes. Gemini will regenerate that day while keeping the rest of your trip intact.',
  },
  {
    q: 'How accurate is the budget tracking?',
    a: 'Gemini estimates costs based on typical prices for each destination and activity type. The budget gauge shows you at a glance if you\'re within, over, or under your budget.',
  },
  {
    q: 'What destinations are supported?',
    a: 'Any destination worldwide! From Tokyo to Timbuktu, Gemini has knowledge of destinations globally and can generate relevant itineraries.',
  },
  {
    q: 'How long does it take to generate a plan?',
    a: 'Most itineraries are generated in 10-20 seconds. Complex requests with many days may take slightly longer.',
  },
  {
    q: 'Can I save or share my itinerary?',
    a: 'Your itinerary is displayed on screen and can be copied or screenshotted. Save functionality coming soon.',
  },
  {
    q: 'What about dietary restrictions and accessibility?',
    a: 'You can specify dietary preferences and accessibility constraints in the form. Gemini takes these into account when planning activities and meal suggestions.',
  },
];

function FaqAccordion({ item, index }: { item: FaqItem; index: number }) {
  const [open, setOpen] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-30px' }}
      transition={{ duration: 0.3, delay: index * 0.03 }}
      className="border-b border-white/5 last:border-0"
    >
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full text-left py-4 px-1 gap-3 cursor-pointer group"
        aria-expanded={open}
      >
        <span className="text-sm text-white/80 group-hover:text-white transition-colors">
          {item.q}
        </span>
        <ChevronDown
          className={`w-4 h-4 text-white/30 shrink-0 transition-transform duration-300 ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <p className="text-sm text-white/50 px-1 pb-4 leading-relaxed">
              {item.a}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function FaqSection() {
  const [searchQuery, setSearchQuery] = useState('');
  const filtered = searchQuery.trim()
    ? faqs.filter(f => f.q.toLowerCase().includes(searchQuery.toLowerCase()) || f.a.toLowerCase().includes(searchQuery.toLowerCase()))
    : faqs;

  return (
    <div className="max-w-2xl mx-auto">
      <div className="relative mb-8">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
        <input
          type="text"
          placeholder="Search FAQs..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-sky-500/50 transition-colors"
          aria-label="Search frequently asked questions"
        />
      </div>
      <div>
        {filtered.map((item, i) => (
          <FaqAccordion key={i} item={item} index={i} />
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            No results found for &quot;{searchQuery}&quot;
          </p>
        )}
      </div>
    </div>
  );
}
