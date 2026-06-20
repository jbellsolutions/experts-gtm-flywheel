// Your offer(s). The framework text (the email spine) is edited in the dashboard
// Leads tab and stored in Supabase app_settings (key offer_framework:<slug>).
export const OFFERS: { slug: string; label: string; live: boolean }[] = [
  { slug: "your_offer", label: "Your Offer", live: true },
];

// Brand voices selectable in the UI. Empty = single-voice (the worker default).
export const VOICES: { id: string; label: string }[] = [];

export const DEFAULT_OFFER = "your_offer";
export const DEFAULT_VOICE = "ai_guy";
