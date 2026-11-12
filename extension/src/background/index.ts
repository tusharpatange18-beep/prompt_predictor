import type { ExtMessage, ExtReply } from "../shared/types";

const BACKEND = "http://127.0.0.1:8000";
const SUGGEST_TIMEOUT_MS = 45_000; // a local model can take a while on first load
const FEEDBACK_TIMEOUT_MS = 5_000;

async function post(path: string, body: unknown, timeoutMs: number): Promise<ExtReply<unknown>> {
  try {
    const res = await fetch(`${BACKEND}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    return { ok: true, data: await res.json() };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.name : "network error" };
  }
}

chrome.runtime.onMessage.addListener((msg: ExtMessage, _sender, sendResponse) => {
  const work =
    msg.type === "SUGGEST"
      ? post("/v1/suggest", msg.payload, SUGGEST_TIMEOUT_MS)
      : post("/v1/feedback", msg.payload, FEEDBACK_TIMEOUT_MS);
  work.then(sendResponse);
  return true; // keep the channel open for the async reply
});
