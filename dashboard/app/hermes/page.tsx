import { supabase } from "@/lib/supabase";
import { HermesChatBox } from "@/components/hermes-chat-box";
import { saveHermesConfig } from "@/app/actions";
import { OFFERS, VOICES } from "@/lib/leadgen-offers";

export const dynamic = "force-dynamic";

// Cold Email — a chat-driven campaign builder. Hermes (a scoped Claude agent on the
// prospect-api service, working from the cold_email_playbook distilled from Single Brain)
// gathers the campaign spec; the worker creates an UNSTARTED SmartLead campaign + ingests
// the leads into Airtable for review. Nothing sends until the operator STARTs it.
export default async function HermesPage() {
  const { data: settings } = await supabase
    .from("app_settings")
    .select("key,value")
    .in("key", ["hermes:business_info", "smartlead:api_key"]);
  const map = Object.fromEntries((settings ?? []).map((r: any) => [r.key, r.value]));
  const businessInfo = map["hermes:business_info"] || "";
  const smartleadSet = !!map["smartlead:api_key"];

  return (
    <div className="space-y-4">
      <div className="card !p-4">
        <h2 className="text-lg font-semibold">📧 Cold Email — chat with Hermes</h2>
        <p className="text-sm text-gray-600 mt-1">
          Tell Hermes who to reach and which offer to sell. It loads the leads (a post&apos;s
          commenters or your uploaded list), verifies + enriches them, drafts a custom email per lead
          in your voice, lands them in your Airtable to review, and sets up an <b>unstarted</b>{" "}
          SmartLead campaign. Nothing sends until you add inboxes and hit START.
        </p>
      </div>

      <details className="card" {...(businessInfo ? {} : { open: true })}>
        <summary className="cursor-pointer text-sm font-medium">
          ⚙ Business info + keys {businessInfo ? "· set ✓" : "· add yours"}
        </summary>
        <form action={saveHermesConfig} className="space-y-2 mt-3">
          <label className="block text-xs font-medium text-gray-500">
            About your business / offer (Hermes uses this to make the copy specific)
          </label>
          <textarea
            name="business_info"
            rows={4}
            defaultValue={businessInfo}
            className="w-full text-sm border border-gray-200 rounded p-2"
            placeholder="What you sell, who it's for, the transformation, proof, the CTA…"
          />
          <label className="block text-xs font-medium text-gray-500">
            SmartLead API key{" "}
            {smartleadSet ? "(saved ✓ — leave blank to keep)" : "(or set SMARTLEAD_API_KEY on the worker)"}
          </label>
          <input
            name="smartlead_api_key"
            type="password"
            autoComplete="off"
            className="w-full text-sm border border-gray-200 rounded p-2"
            placeholder={smartleadSet ? "••••••••" : "your SmartLead API key"}
          />
          <button className="btn btn-ok text-xs" type="submit">
            Save
          </button>
        </form>
      </details>

      <HermesChatBox businessInfo={businessInfo} offers={OFFERS} voices={VOICES} />
    </div>
  );
}
