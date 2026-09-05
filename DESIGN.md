# VoyagerAI — Design System

## Visual World: Brodovitch Bazaar Spread

Inspired by Harper's Bazaar under Alexey Brodovitch (1934–58). The travel magazine spread as a living interface — warm white paper, hairline typography, destination photography choreographed across the gutter.

## Palette

| Token            | OKLCH                | Hex approx | Role                        |
|------------------|----------------------|------------|-----------------------------|
| `background`     | `oklch(0.97 0.008 75)` | `#f7f3ed` | Warm white paper ground     |
| `foreground`     | `oklch(0.22 0.015 50)` | `#2a2520` | Charcoal ink                |
| `card`           | `oklch(0.99 0.004 75)` | `#fdfbf7` | Slightly lighter paper      |
| `primary`        | `oklch(0.52 0.19 32)`  | `#c44536` | Cinnabar red accent         |
| `secondary`      | `oklch(0.94 0.012 60)` | `#ebe6dc` | Warm muted                  |
| `muted`          | `oklch(0.94 0.008 70)` | `#ece8e0` | Subtle background           |
| `muted-foreground` | `oklch(0.50 0.012 55)` | `#7a7367` | Secondary text            |
| `accent`         | `oklch(0.92 0.025 45)` | `#e8d5c4` | Terracotta warmth           |
| `accent-foreground` | `oklch(0.35 0.04 35)` | `#8a5a3a` | Terracotta text           |
| `destructive`    | `oklch(0.52 0.22 27)`  | `#c33a2a` | Error/destructive           |
| `border`         | `oklch(0.89 0.006 70)` | `#d9d4ca` | Hairline rules              |
| `chart-1`        | `oklch(0.52 0.19 32)`  | Cinnabar   | Primary chart color         |
| `chart-2`        | `oklch(0.58 0.14 145)` | Sage       | Secondary chart color       |
| `chart-3`        | `oklch(0.68 0.12 85)`  | Ochre      | Tertiary chart color        |

## Typography

- **Display/Headings**: Geist Sans, bold, tight tracking, large sizes (3xl–7xl)
- **Body**: Geist Sans, regular, relaxed leading
- **Mono/Labels**: Geist Mono, small sizes, wide tracking for step numbers and data labels
- **Italic**: Used for accent words in hero headlines (cinnabar primary color)

## Spacing & Layout

- **Section padding**: `py-24 md:py-32` for major sections, `py-20 md:py-24` for stats
- **Container**: `max-w-5xl mx-auto px-6` (content), `max-w-3xl` (CTA), `max-w-4xl` (stats)
- **Grid dividers**: `gap-px bg-border` creates hairline grid separators between cards
- **Card padding**: `p-8 md:p-10` for feature/steps, generous negative space

## Motion

- `paper-drift`: 12s ease-in-out infinite, subtle 8px drift for ambient elements
- `ink-spread`: 0.8s cubic-bezier(0.22, 1, 0.36, 1), blur-to-focus entrance
- `fadeSlideUp`: Standard 20px slide-up entrance
- `shimmer`: Loading placeholder animation
- All motion respects `prefers-reduced-motion`

## Components

### HeroSection
- Full-bleed destination photograph (left, 50% width on desktop)
- Cinnabar hairline rule as the gutter seam (1px, `bg-primary/40`)
- Editorial text right side: large headline with italic accent, description, CTAs
- No aurora, no blur, no gradient text

### HowItWorks
- Three-column grid with hairline dividers (`gap-px bg-border`)
- Mono step numbers in cinnabar (`text-primary font-mono`)
- Left-aligned heading, no centered badge or icon

### FeatureGrid
- Two-column grid with hairline dividers
- Mono feature numbers (01–06) in cinnabar
- No icons, no gradient cards, no spotlight effects

### StatsSection
- Four-column grid with hairline dividers
- Large tabular numbers, small tracking-wide labels
- No icon boxes, no hover scale effects

### CTASection
- Cinnabar hairline rule (12px × 1px) above heading
- Clean primary button, no gradient

### Navbar
- Cinnabar hairline accent (`w-1 h-5 bg-primary rounded-full`) as brand mark
- No gradient logo box, no Sparkles icon
- Transparent → `bg-white/80 backdrop-blur-xl` on scroll

### Footer
- Cinnabar hairline accent as brand mark
- Clean text links, no translate effects

### ThreadSidebar (Chat)
- Cinnabar hairline accent as brand mark
- Clean `bg-sidebar` background, hairline borders (`border-border/50`)

### ComparisonView
- Three tiers: sage (budget), cinnabar (balanced), terracotta (premium)
- Uses chart tokens instead of hardcoded colors

## What Was Removed

- All indigo/violet/blue gradient backgrounds and buttons
- All aurora and float-slow blur animations
- All gradient text (`bg-clip-text text-transparent`)
- All colored icon boxes with gradient backgrounds
- All SpotlightCard effects
- All emerald/amber/rose/cyan hardcoded colors
- All `red-500`/`red-600` hardcoded colors (replaced with `destructive` token)
- All `amber-500`/`amber-600` hardcoded colors (replaced with `accent` token)
- All `green-500` hardcoded colors (replaced with `chart-2` token)
- All Sparkles icons used as decorative logo elements

## Direction Contract

Located in `frontend/app/layout.tsx` as an HTML comment on the body element.
