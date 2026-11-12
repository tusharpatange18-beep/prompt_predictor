import { findInput, readDraft, writeDraft } from "../sites/chatgpt";
import { debounce } from "../shared/debounce";
import { restorePII, stripPII } from "../shared/pii";
import type { ExtMessage, ExtReply, FeedbackAction, SuggestResponse } from "../shared/types";
import { hideCard, showCard } from "./card";

const DEBOUNCE_MS = 400;
const MIN_CHARS = 8;

let attached: HTMLElement | null = null;
let shownId: string | null = null; // suggestion currently on screen
let accepted: { id: string; text: string } | null = null; // inserted, waiting to see if the user edits it

function send<T>(msg: ExtMessage): Promise<ExtReply<T>> {
  return chrome.runtime.sendMessage(msg);
}

function sendFeedback(id: string, action: FeedbackAction) {
  send({ type: "FEEDBACK", payload: { suggestion_id: id, action } }).catch(() => {});
}

function dismiss() {
  if (shownId) sendFeedback(shownId, "dismissed");
  shownId = null;
  hideCard();
}

const onDraftSettled = debounce(async (el: HTMLElement) => {
  const draft = readDraft(el).trim();

  if (accepted && draft !== accepted.text) {
    sendFeedback(accepted.id, "edited");
    accepted = null;
  }

  if (draft.length < MIN_CHARS) {
    shownId = null;
    hideCard();
    return;
  }

  const { text, map } = stripPII(draft);
  let reply: ExtReply<SuggestResponse>;
  try {
    reply = await send<SuggestResponse>({
      type: "SUGGEST",
      payload: { draft: text, similar_prompts: [], recent_messages: [], site: "chatgpt" },
    });
  } catch {
    return; // extension was reloaded; this content script is orphaned
  }

  if (readDraft(el).trim() !== draft) return; // user kept typing; this answer is stale
  if (!reply.ok || !reply.data.show_suggestion) {
    shownId = null;
    hideCard();
    return;
  }

  const { suggestion_id, suggestions } = reply.data;
  shownId = suggestion_id;
  showCard(el, {
    suggestions: suggestions.map((s) => restorePII(s, map)),
    onAccept: (chosen) => {
      writeDraft(el, chosen);
      accepted = { id: suggestion_id, text: chosen.trim() };
      shownId = null;
      hideCard();
      sendFeedback(suggestion_id, "accepted");
    },
    onDismiss: dismiss,
  });
}, DEBOUNCE_MS);

function tryAttach() {
  const el = findInput();
  if (!el || el === attached) return;
  attached = el;
  el.addEventListener("input", () => onDraftSettled(el));
}

tryAttach();
new MutationObserver(tryAttach).observe(document.body, {
  childList: true,
  subtree: true,
});
