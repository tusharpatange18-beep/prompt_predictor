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

/** Sends a message to the service worker (background/index.ts), which calls the backend. */
function send<T>(msg: ExtMessage): Promise<ExtReply<T>> {
  return chrome.runtime.sendMessage(msg);
}

/** Tells the backend what the user did with a suggestion. Errors are ignored: it's only a log. */
function sendFeedback(id: string, action: FeedbackAction) {
  send({ type: "FEEDBACK", payload: { suggestion_id: id, action: action } }).catch(function () {
    // ignore
  });
}

/** The user closed the card with the x button. */
function dismiss() {
  if (shownId) {
    sendFeedback(shownId, "dismissed");
  }
  shownId = null;
  hideCard();
}

function hideSuggestion() {
  shownId = null;
  hideCard();
}

// Runs once the user has stopped typing for DEBOUNCE_MS
const onDraftSettled = debounce(async function (el: HTMLElement) {
  const draft = readDraft(el).trim();

  // The user changed a rewrite they had accepted: record that as "edited"
  if (accepted && draft !== accepted.text) {
    sendFeedback(accepted.id, "edited");
    accepted = null;
  }

  // Too short to judge yet
  if (draft.length < MIN_CHARS) {
    hideSuggestion();
    return;
  }

  // Personal data never leaves the browser: send placeholders, keep the map here
  const stripped = stripPII(draft);
  let reply: ExtReply<SuggestResponse>;
  try {
    reply = await send<SuggestResponse>({
      type: "SUGGEST",
      payload: { draft: stripped.text, similar_prompts: [], recent_messages: [], site: "chatgpt" },
    });
  } catch {
    return; // extension was reloaded; this content script is orphaned
  }

  // The user kept typing while we waited: this answer is for an old draft
  if (readDraft(el).trim() !== draft) {
    return;
  }
  if (!reply.ok || !reply.data.show_suggestion) {
    hideSuggestion();
    return;
  }

  const suggestionId = reply.data.suggestion_id;
  // Put the real values back into each rewrite before showing it
  const rewrites: string[] = [];
  for (const suggestion of reply.data.suggestions) {
    rewrites.push(restorePII(suggestion, stripped.map));
  }

  shownId = suggestionId;
  showCard(el, {
    suggestions: rewrites,
    onAccept: function (chosen) {
      writeDraft(el, chosen); // replace the user's text with the chosen rewrite
      accepted = { id: suggestionId, text: chosen.trim() };
      hideSuggestion();
      sendFeedback(suggestionId, "accepted");
    },
    onDismiss: dismiss,
  });
}, DEBOUNCE_MS);

/** Starts listening to ChatGPT's message box (once per box). */
function tryAttach() {
  const el = findInput();
  if (!el || el === attached) {
    return; // no box yet, or already listening to this one
  }
  attached = el;
  el.addEventListener("input", function () {
    onDraftSettled(el);
  });
}

tryAttach();
// ChatGPT is a single-page app that redraws the box (e.g. new chat), so check again on every page change
new MutationObserver(tryAttach).observe(document.body, {
  childList: true,
  subtree: true,
});
