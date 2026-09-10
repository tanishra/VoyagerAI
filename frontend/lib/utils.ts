import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Strip <comparison>...</comparison> and <itinerary>...</itinerary> blocks
 * from text. Handles both complete blocks and partial/incomplete tags
 * that may appear during streaming (opening tag without closing tag).
 */
export function stripStructuredTags(text: string): string {
  if (!text) return text;
  let result = text;
  // Remove complete blocks first
  result = result.replace(/<comparison>[\s\S]*?<\/comparison>/g, '');
  result = result.replace(/<itinerary>[\s\S]*?<\/itinerary>/g, '');
  // Remove partial blocks (opening tag without closing — during streaming)
  result = result.replace(/<comparison>[\s\S]*$/g, '');
  result = result.replace(/<itinerary>[\s\S]*$/g, '');
  // Clean up any leftover empty lines
  return result.replace(/\n{3,}/g, '\n\n').trim();
}
