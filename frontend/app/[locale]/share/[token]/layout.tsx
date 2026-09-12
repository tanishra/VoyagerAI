import type { Metadata } from 'next';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchShareData(token: string) {
  try {
    const res = await fetch(`${API_URL}/share/${token}`, { next: { revalidate: 0 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const data = await fetchShareData(token);

  if (!data) {
    return {
      title: 'Shared Itinerary — VoyagerAI',
      description: 'View this shared travel itinerary on VoyagerAI.',
    };
  }

  const destination = data.destination || 'Trip';
  const days = data.itinerary?.total_days ?? 0;
  const cost = data.itinerary?.estimated_total_cost_usd ?? 0;

  const images = data.image_base64
    ? [{ url: `data:image/png;base64,${data.image_base64}`, width: 1200, height: 630 }]
    : undefined;

  return {
    title: `Trip to ${destination} — ${days} days`,
    description: `Check out this ${days}-day itinerary for ${destination}, planned with VoyagerAI. Total cost: $${cost}.`,
    openGraph: {
      title: `Trip to ${destination} — ${days} days`,
      description: `Check out this ${days}-day itinerary for ${destination}, planned with VoyagerAI. Total cost: $${cost}.`,
      type: 'website',
      images,
    },
    twitter: {
      card: 'summary_large_image',
      title: `Trip to ${destination} — ${days} days`,
      description: `Check out this ${days}-day itinerary for ${destination}, planned with VoyagerAI.`,
      images,
    },
  };
}

export default function ShareLayout({ children }: { children: React.ReactNode }) {
  return children;
}
