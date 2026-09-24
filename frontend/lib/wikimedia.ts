async function fetchCommonsImage(searchQuery: string): Promise<string | null> {
  try {
    const searchUrl = `https://commons.wikimedia.org/w/api.php?action=query&format=json&origin=*&generator=search&gsrsearch=${encodeURIComponent(searchQuery)}&gsrnamespace=6&gsrlimit=1&prop=imageinfo&iiprop=url&iiurlwidth=400`;
    const res = await fetch(searchUrl);
    const data = await res.json();
    const pages = data?.query?.pages;
    if (!pages) return null;

    const page = Object.values(pages)[0] as { imageinfo?: [{ thumburl?: string }] } | undefined;
    return page?.imageinfo?.[0]?.thumburl ?? null;
  } catch {
    return null;
  }
}

async function fetchWikipediaThumb(searchQuery: string): Promise<string | null> {
  try {
    // Article search + pageimages thumbnail — far better hit rate than
    // Commons filename search for real-world POIs ("India Gate", etc.).
    const url = `https://en.wikipedia.org/w/api.php?action=query&format=json&origin=*&generator=search&gsrsearch=${encodeURIComponent(searchQuery)}&gsrlimit=1&prop=pageimages&piprop=thumbnail&pithumbsize=400`;
    const res = await fetch(url);
    const data = await res.json();
    const pages = data?.query?.pages;
    if (!pages) return null;

    const page = Object.values(pages)[0] as { thumbnail?: { source?: string } } | undefined;
    return page?.thumbnail?.source ?? null;
  } catch {
    return null;
  }
}

export async function fetchWikimediaImage(searchQuery: string): Promise<string | null> {
  // Kept for destination-level callers — single-query Commons lookup.
  return (await fetchWikipediaThumb(searchQuery)) ?? (await fetchCommonsImage(searchQuery));
}

export async function fetchActivityImage(
  activity: string,
  location: string,
  destination: string,
): Promise<string | null> {
  // Try the most specific real-world names first — Wikipedia article search
  // resolves POI names well; Commons file search is the last resort.
  const candidates = [
    location && `${location} ${destination}`,
    location,
    activity && `${activity} ${destination}`,
    activity,
    destination,
  ].filter((q): q is string => Boolean(q?.trim()));

  for (const q of candidates) {
    const url = await fetchWikipediaThumb(q);
    if (url) return url;
  }
  for (const q of candidates) {
    const url = await fetchCommonsImage(q);
    if (url) return url;
  }
  return null;
}
