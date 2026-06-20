const CHANNELS = [
  { id: "comment", label: "Comment", needsPost: true },
  { id: "cold_dm", label: "Cold DM" },
  { id: "connection_note", label: "Connection note" },
  { id: "dm_reply", label: "DM reply", needsThread: true },
  { id: "email", label: "Email" },
  { id: "sms", label: "SMS" },
];
const VOICES = [
  { id: "ai_guy", label: "AI Guy" },
  { id: "human_loop", label: "Human-Loop" },
  { id: "ai_reality", label: "AI Reality" },
];

let channel = "comment";
let voice = "ai_guy";

function chips(container, items, current, onPick) {
  container.innerHTML = "";
  items.forEach((it) => {
    const b = document.createElement("button");
    b.className = "chip" + (it.id === current() ? " on" : "");
    b.textContent = it.label;
    b.onclick = () => { onPick(it.id); render(); };
    container.appendChild(b);
  });
}
function render() {
  chips(document.getElementById("channels"), CHANNELS, () => channel, (v) => (channel = v));
  chips(document.getElementById("voices"), VOICES, () => voice, (v) => (voice = v));
  const cfg = CHANNELS.find((c) => c.id === channel);
  document.getElementById("postLabel").textContent = cfg.needsThread
    ? "Conversation so far (paste the thread)"
    : cfg.needsPost ? "The post to react to (highlight on page, or paste)"
    : "Optional: a recent post of theirs (highlight, or paste)";
}

// Grab {url, selection, og} from the active tab.
async function grabContext() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return {};
    const [res] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => ({
        url: location.href,
        selection: (window.getSelection()?.toString() || "").trim(),
        og: (document.querySelector('meta[property="og:description"]')?.content || "").trim(),
        title: document.title,
      }),
    });
    return res?.result || {};
  } catch { return {}; }
}

async function generate() {
  const { dashUrl, password } = await chrome.storage.local.get(["dashUrl", "password"]);
  const errEl = document.getElementById("err");
  const out = document.getElementById("results");
  errEl.textContent = ""; out.innerHTML = "";
  const go = document.getElementById("go");
  go.disabled = true; go.textContent = "Generating…";
  try {
    const prospect = document.getElementById("prospect").value.trim();
    const post = document.getElementById("post").value.trim();
    const cfg = CHANNELS.find((c) => c.id === channel);
    const body = {
      channel, voice,
      prospect_text: prospect || null,
      post_text: cfg.needsThread ? null : (post || null),
      thread_text: cfg.needsThread ? (post || null) : null,
    };
    const r = await fetch(`${dashUrl.replace(/\/$/, "")}/api/prospect`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Basic " + btoa("va:" + password),
      },
      body: JSON.stringify(body),
    });
    const text = await r.text();
    if (!r.ok) { errEl.textContent = `API ${r.status}: ${text.slice(0, 160)}`; return; }
    const data = JSON.parse(text);
    (data.variants || []).forEach((v, i) => {
      const div = document.createElement("div");
      div.className = "variant";
      const subj = v.subject ? `Subject: ${v.subject}\n\n` : "";
      div.textContent = subj + v.text;
      const copy = document.createElement("button");
      copy.className = "copy"; copy.textContent = "Copy";
      copy.onclick = () => { navigator.clipboard.writeText(subj + v.text); copy.textContent = "Copied ✓"; };
      div.appendChild(document.createElement("br"));
      div.appendChild(copy);
      out.appendChild(div);
    });
    if (!(data.variants || []).length) errEl.textContent = "No variants returned.";
  } catch (e) {
    errEl.textContent = String(e?.message || e);
  } finally {
    go.disabled = false; go.textContent = "Generate 3 variants";
  }
}

// Send a post URL to the dashboard → queues a lead-gen job that scrapes the
// post's commenters, enriches them, and drafts an offer email each. Uses the
// pasted link if there is one, else falls back to the current tab's URL.
async function scrapePost() {
  const { dashUrl, password } = await chrome.storage.local.get(["dashUrl", "password"]);
  const msg = document.getElementById("scrapeMsg");
  const btn = document.getElementById("scrape");
  msg.textContent = ""; btn.disabled = true; btn.textContent = "Queuing…";
  try {
    let postUrl = (document.getElementById("scrapeUrl").value || "").trim();
    if (!postUrl) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      postUrl = tab?.url || "";
    }
    if (!/^https?:\/\//.test(postUrl)) {
      msg.textContent = "Paste a LinkedIn post URL (or open the post in this tab).";
      return;
    }
    const r = await fetch(`${dashUrl.replace(/\/$/, "")}/api/leadgen`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Basic " + btoa("bdr:" + password) },
      body: JSON.stringify({ post_url: postUrl }),
    });
    const text = await r.text();
    msg.textContent = r.ok
      ? "Queued ✓ — commenters get scraped, enriched + emailed on the dashboard Leads tab (~2 min)."
      : `API ${r.status}: ${text.slice(0, 120)}`;
  } catch (e) {
    msg.textContent = String(e?.message || e);
  } finally {
    btn.disabled = false; btn.textContent = "🧲 Scrape this post → leads";
  }
}

(async function init() {
  const { dashUrl, password } = await chrome.storage.local.get(["dashUrl", "password"]);
  if (!dashUrl || !password) {
    document.getElementById("needsConfig").style.display = "block";
    document.getElementById("openOpts").onclick = () => chrome.runtime.openOptionsPage();
    return;
  }
  document.getElementById("app").style.display = "block";
  render();
  const ctx = await grabContext();
  document.getElementById("prospect").value = ctx.url ? `${ctx.title || ""}\n${ctx.url}` : "";
  document.getElementById("post").value = ctx.selection || ctx.og || "";
  // Pre-fill the scrape field when the tab is already a LinkedIn post (editable).
  if (/linkedin\.com\/(posts\/|feed\/update\/|.*activity-)/i.test(ctx.url || "")) {
    document.getElementById("scrapeUrl").value = ctx.url;
  }
  document.getElementById("go").onclick = generate;
  document.getElementById("scrape").onclick = scrapePost;
})();
