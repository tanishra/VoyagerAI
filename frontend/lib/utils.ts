import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Strip <comparison>...</comparison> and <itinerary>...</itinerary> blocks
 * from text. Handles both complete blocks and partial/incomplete tags
 * that may appear during streaming (opening tag without closing tag).
 * Also truncates untagged multi-tier plan prose ("Budget Plan\n- Total Cost…")
 * — the comparison card is the single source of truth for that content.
 */
export function stripStructuredTags(text: string): string {
  if (!text) return text;
  let result = text;
  // Remove complete blocks first
  result = result.replace(/<comparison>[\s\S]*?<\/comparison>/g, '');
  result = result.replace(/<itinerary>[\s\S]*?<\/itinerary>/g, '');
  result = result.replace(/<clarify_answers>[\s\S]*?<\/clarify_answers>/g, '');
  // Remove partial blocks (opening tag without closing — during streaming)
  result = result.replace(/<comparison>[\s\S]*$/g, '');
  result = result.replace(/<itinerary>[\s\S]*$/g, '');
  result = result.replace(/<clarify_answers>[\s\S]*$/g, '');
  // Untagged plan prose: when 2+ "X Plan" tier headers appear, the plans are
  // rendered as a card — truncate the prose at the first tier header.
  const tierHeaders = result.match(/^\s*(?:#{1,4}\s*|\*\*)?\s*(?:budget|balanced|premium|luxury|economy|standard)\s+plan\b/gim);
  if (tierHeaders && new Set(tierHeaders.map((h) => h.toLowerCase())).size >= 2) {
    const first = result.search(/^\s*(?:#{1,4}\s*|\*\*)?\s*(?:budget|balanced|premium|luxury|economy|standard)\s+plan\b/im);
    if (first > 0) {
      const leadIn = result.slice(0, first).trim();
      result = leadIn ? `${leadIn}\n\nSee the plans below.` : 'See the plans below.';
    }
  }
  // Clean up any leftover empty lines
  return result.replace(/\n{3,}/g, '\n\n').trim();
}
