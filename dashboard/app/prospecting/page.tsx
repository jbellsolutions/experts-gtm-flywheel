import { ProspectingForm } from "@/components/prospecting-form";

export const dynamic = "force-dynamic";

export default function ProspectingPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Prospecting</h1>
        <p className="text-sm text-gray-500">
          Generate on-voice outreach in you&apos;s your brand voice — tailored to the
          prospect and the specific post/conversation. Paste a LinkedIn URL (we&apos;ll
          try to pull it) or just paste the text. Review, tweak, and send manually.
        </p>
      </div>
      <ProspectingForm />
    </div>
  );
}
