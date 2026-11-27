// Service worker: the only part of the extension that talks to our backend.
// The content script (inside ChatGPT) sends it messages; it does the HTTP call and replies.
import type { ExtMessage, ExtReply } from "../shared/types";

const BACKEND = "http://127.0.0.1:8000";
const SUGGEST_TIMEOUT_MS = 45_000; // a local model can take a while on first load
const FEEDBACK_TIMEOUT_MS = 5_000;

/** POSTs JSON to the backend. Never throws: failures come back as { ok: false, error }. */
async function post(path: string, body: unknown, timeoutMs: number): Promise<ExtReply<unknown>> {
  try {
    const res = await fetch(BACKEND + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs), // give up after timeoutMs
    });
    if (!res.ok) {
      return { ok: false, error: "HTTP " + res.status };
    }
    return { ok: true, data: await res.json() };
  } catch (e) {
    // e.g. "TimeoutError" when the backend is too slow, or the server is not running
    if (e instanceof Error) {
      return { ok: false, error: e.name };
    }
    return { ok: false, error: "network error" };
  }
}

chrome.runtime.onMessage.addListener(function (msg: ExtMessage, _sender, sendResponse) {
  let work: Promise<ExtReply<unknown>>;
  if (msg.type === "SUGGEST") {
    work = post("/v1/suggest", msg.payload, SUGGEST_TIMEOUT_MS);
  } else {
    work = post("/v1/feedback", msg.payload, FEEDBACK_TIMEOUT_MS);
  }
  work.then(sendResponse);
  return true; // keep the channel open for the async reply
});
