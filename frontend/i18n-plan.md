# Multi-Language Support Implementation Plan

## Overview

Full i18n support for Voyager AI using `next-intl` across 6 locales: English, Spanish, French, German, Hindi, Japanese.

## Completed Steps

### Step 1: Install next-intl + configure plugin
- Installed `next-intl` package
- Configured `next-intl` plugin in `next.config.ts`
- Created `i18n.ts` with `getRequestConfig` for server-side locale detection
- Locale resolution: cookie (`NEXT_LOCALE`) → `Accept-Language` header → default (`en`)

### Step 2: Create 6 message catalogs
- Created `frontend/messages/{en,es,fr,de,hi,ja}.json`
- 15 namespaces: `nav`, `chat`, `status`, `itinerary`, `comparison`, `preferences`, `auth`, `about`, `faq`, `home`, `footer`, `offline`, `install`, `threads`, `common`
- All catalogs have matching keys across locales

### Step 3: IntlProvider + useLocale hook
- `app/layout.tsx`: Wrapped app with `NextIntlClientProvider` using server-side `getLocale` + `getMessages`
- `lib/useLocale.ts`: Client hook wrapping `next-intl`'s `useLocale` with fallback, plus `setLocale` function (cookie + localStorage + page reload)
- Dynamic `<html lang>` attribute

### Step 4: Language switcher in Navbar
- `components/LanguageSwitcher.tsx`: Dropdown with flags and locale names
- Integrated into `components/Navbar.tsx`
- Calls `setLocale()` on selection

### Step 5: Replace hardcoded strings with useTranslations()
Components updated:
- `components/Navbar.tsx` — nav links, auth buttons, aria-labels
- `app/chat/page.tsx` — welcome, errors, status, buttons, placeholders, tool labels
- `components/ItineraryCard.tsx` — export/share, details, map, packing, warnings
- `app/chat/ComparisonView.tsx` — tier labels, cost breakdown, tradeoffs, matrix
- `components/OfflineBanner.tsx` — offline/replaying/online messages
- `components/InstallPrompt.tsx` — install button, dismiss
- `app/chat/ThreadSidebar.tsx` — new chat, threads, shared links, delete confirm
- `components/ItineraryMap.tsx` — day labels, slot labels, popups, map unavailable
- `app/login/page.tsx` — sign in prompt, Google button, privacy note
- `app/preferences/page.tsx` — title, file label, save/saved/error states
- `app/about/page.tsx` — badge, title, highlights, how it works, steps
- `app/faq/page.tsx` + `components/FaqSection.tsx` — title, search, Q&A items
- `components/HeroSection.tsx` — badge, hero lines, description, CTAs, features
- `components/FeatureGrid.tsx` — section title, feature titles/descriptions
- `components/HowItWorks.tsx` — badge, title, step titles/descriptions
- `components/StatsSection.tsx` — stat labels
- `components/CTASection.tsx` — title, description, button
- `components/Footer.tsx` — brand, links, tagline

### Step 6: Locale-aware currency formatting
- `lib/format.ts`: `formatCurrency()`, `formatNumber()`, `getCurrencySymbol()`
- Currency map: en→USD, es/fr/de→EUR, hi→INR, ja→JPY
- JPY formatted with 0 decimal places

### Step 7: Backend — Accept-Language + prompt injection
- `backend/models.py`: Added `locale` field to `ChatRequest`
- `backend/agents/prompts.py`: Added `LANGUAGE_INSTRUCTIONS` map for 6 locales, `build_chat_agent_prompt(locale)` function
- Language block injected into system prompt for non-English locales
- `backend/agents/deep_agent.py`: `create_chat_agent()` and `stream_chat_agent()` accept `locale` param
- `backend/main.py`: `chat_stream` extracts locale from `chat_req.locale` → `Accept-Language` header → fallback

### Step 8: Frontend — send locale with chat requests
- `lib/chat-api.ts`: `streamChat` body type includes `locale`, sends `Accept-Language` header
- `app/chat/page.tsx`: Uses `useLocale()` hook, passes locale to both `streamChat` calls (normal + replay)

### Step 9: Tests
- `frontend/tests/format.test.ts`: 10 tests for currency/number formatting across locales
- `backend/tests/test_prompt_locale.py`: 9 tests for prompt injection (all locales, edge cases)
- `frontend/tests/setup.ts`: Added `next-intl` and `@/lib/useLocale` mocks using English catalog
- All 107 existing frontend tests pass with new mocks
- All 9 backend prompt tests pass

### Step 10: Verification
- TypeScript compiles cleanly (`tsc --noEmit` passes)
- All 6 message catalogs have 15 namespaces with matching keys
- Frontend: 21 test files, 107 tests pass
- Backend: 9 prompt locale tests pass

## Architecture

```
User selects locale → setLocale() → cookie + localStorage + reload
                        ↓
Server: i18n.ts reads cookie/Accept-Language → getLocale() + getMessages()
                        ↓
layout.tsx: NextIntlClientProvider wraps app with locale + messages
                        ↓
Components: useTranslations('namespace') → t('key', { params })
                        ↓
Chat requests: locale sent in body + Accept-Language header
                        ↓
Backend: chat_stream extracts locale → build_chat_agent_prompt(locale)
                        ↓
Agent: system prompt includes <language> block → AI responds in target language
```

## Files Modified/Created

### Frontend
- `i18n.ts` — locale config + server-side resolution
- `next.config.ts` — next-intl plugin
- `app/layout.tsx` — NextIntlClientProvider wrapper
- `lib/useLocale.ts` — client hook + setLocale
- `lib/format.ts` — locale-aware currency/number formatting (new)
- `lib/chat-api.ts` — locale in request body + header
- `components/LanguageSwitcher.tsx` — dropdown UI (new)
- `components/Navbar.tsx`, `Footer.tsx`, `HeroSection.tsx`, `FeatureGrid.tsx`, `HowItWorks.tsx`, `StatsSection.tsx`, `CTASection.tsx`, `OfflineBanner.tsx`, `InstallPrompt.tsx`, `ItineraryCard.tsx`, `ItineraryMap.tsx`, `FaqSection.tsx`
- `app/chat/page.tsx`, `app/chat/ThreadSidebar.tsx`, `app/chat/ComparisonView.tsx`
- `app/login/page.tsx`, `app/preferences/page.tsx`, `app/about/page.tsx`, `app/faq/page.tsx`
- `messages/{en,es,fr,de,hi,ja}.json` — 6 message catalogs
- `tests/setup.ts` — next-intl mock
- `tests/format.test.ts` — formatting tests (new)

### Backend
- `models.py` — locale field in ChatRequest
- `agents/prompts.py` — LANGUAGE_INSTRUCTIONS + build_chat_agent_prompt
- `agents/deep_agent.py` — locale param threading
- `main.py` — locale extraction + passing
- `tests/test_prompt_locale.py` — prompt injection tests (new)

## Post-Deploy Fix: Server-Only Import Error

### Problem
Vercel build failed with:
```
Error: You're importing a module that depends on "next/headers". This API is only available in Server Components
```

`i18n.ts` imports `next/headers` (server-only), but client components (`useLocale.ts`, `format.ts`, `LanguageSwitcher.tsx`) were importing constants/types from `@/i18n`, creating an invalid server→client import chain.

### Fix
- Created `lib/i18n-config.ts` with all client-safe constants (`locales`, `Locale` type, `defaultLocale`, `localeNames`, `localeFlags`)
- All client components now import from `@/lib/i18n-config` instead of `@/i18n`
- `i18n.ts` re-exports from `i18n-config.ts` for backward compatibility (server components can still use `@/i18n`)

### Files Changed
- `lib/i18n-config.ts` — new file with client-safe constants (new)
- `i18n.ts` — re-exports from `i18n-config.ts` instead of defining constants inline
- `lib/useLocale.ts` — import from `@/lib/i18n-config`
- `lib/format.ts` — import from `@/lib/i18n-config`
- `components/LanguageSwitcher.tsx` — import from `@/lib/i18n-config`

## Enhancement: Locale-Aware Currency Display + Locale-Prefixed Routes + Tests

### Task 1: formatCurrency() in UI Components
- `components/ItineraryCard.tsx` — replaced hardcoded `$` with `formatCurrency(cost, locale)` for total cost and daily cost; added `useLocale()` and `formatCurrency` imports
- `app/chat/ComparisonView.tsx` — replaced hardcoded `$` in PlanCard header, cost breakdown grid, and comparison matrix table with `formatCurrency()` calls; added `useLocale()` to both `PlanCard` and `ComparisonView` components
- `lib/format.ts` — added `minimumFractionDigits: 0` to drop unnecessary `.00` for whole numbers while keeping cents when present
- `tests/ComparisonView.test.tsx` — updated assertions to match locale-formatted currency with thousands separators (`$1,200` instead of `$1200`)

### Task 2: Locale-Prefixed Routes
- `middleware.ts` — new `next-intl/middleware` with `localePrefix: 'always'`; excludes `/api`, `/_next`, `/auth`, `/export`, `/share` from locale routing
- `app/[locale]/layout.tsx` — new locale-scoped layout with `NextIntlClientProvider`, `Navbar`, `Footer`, `SmoothScroll`; `generateStaticParams` for all 6 locales; `setRequestLocale` for static rendering
- `app/layout.tsx` — simplified to pass-through (returns `children` directly); metadata + viewport stay at root
- `app/export/layout.tsx`, `app/share/layout.tsx` — new layouts for non-locale routes with `getLocale`/`getMessages` for IntlProvider
- `app/auth/layout.tsx` — minimal html/body layout for auth callback (no i18n needed)
- `i18n.ts` — `getRequestConfig` now accepts `requestLocale` from `[locale]` segment, falls back to cookie/header detection
- `lib/useLocale.ts` — `setLocale()` now navigates to `/{locale}{pathname}` instead of cookie+reload
- `components/Navbar.tsx` — all nav links use `/${locale}` prefix; logo links to `/${locale}`; logout redirects to `/${locale}/login`
- `components/Footer.tsx` — all footer links use `/${locale}` prefix
- Moved all pages under `app/[locale]/`: `page.tsx`, `about/`, `chat/`, `faq/`, `login/`, `preferences/`, `plan/`
- Updated test imports: `ComparisonView.test.tsx`, `ThreadSidebar.test.tsx`, `ShareManagement.test.tsx`, `HomePage.test.tsx`, `Navbar.test.tsx`
- `next build` generates all 6 locale-prefixed routes (`/en/chat`, `/es/chat`, `/fr/about`, etc.)

### Task 3: Backend Locale Integration Test
- `backend/tests/test_locale_integration.py` — 5 tests verifying locale flows through `chat_stream` → `stream_chat_agent`:
  1. Locale in request body → passed to agent
  2. Locale from `Accept-Language` header → extracted and passed
  3. Body locale takes priority over header
  4. No locale → `None` passed
  5. Unsupported locale in header → `None` fallback
- Uses `monkeypatch` to mock `stream_chat_agent` with capturing async generator
- Auth bypass via `config.settings.AUTH_DEV_BYPASS = True`

### Task 4: Translation Completeness Audit
- `frontend/tests/i18n-audit.test.ts` — 6 tests (one per non-EN locale + sanity check):
  - Flattens all keys recursively from each locale catalog
  - Asserts no missing keys (keys in `en` but not in target locale)
  - Asserts no extra keys (keys in target locale but not in `en`)
  - Asserts `en` has at least 100 keys (sanity)
- All 204 keys match across all 6 locales (verified at implementation time)

### Verification
- Frontend: 113 tests pass (22 test files), `tsc` clean, `next build` green with all 6 locale routes
- Backend: 5 locale integration tests pass
- Translation audit: 6 tests pass, 204 keys match across all locales
