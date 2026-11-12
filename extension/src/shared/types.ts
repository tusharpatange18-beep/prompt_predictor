export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SuggestRequest {
  draft: string;
  similar_prompts: string[];
  recent_messages: ChatMessage[];
  site: string;
}

export interface SuggestResponse {
  suggestion_id: string;
  score: number;
  show_suggestion: boolean;
  missing: string[];
  suggestions: string[];
  conflicts: string[];
}

export type FeedbackAction = "accepted" | "edited" | "dismissed";

export interface FeedbackRequest {
  suggestion_id: string;
  action: FeedbackAction;
}

// Messages from the content script to the service worker.
export type ExtMessage =
  | { type: "SUGGEST"; payload: SuggestRequest }
  | { type: "FEEDBACK"; payload: FeedbackRequest };

export type ExtReply<T> = { ok: true; data: T } | { ok: false; error: string };
