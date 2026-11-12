// Suggestion card, rendered in a shadow root so ChatGPT's CSS can't touch it
// and ours can't leak into the page.

export interface CardOptions {
  suggestions: string[];
  onAccept: (text: string) => void;
  onDismiss: () => void;
}

const STYLE = `
  .card { font: 14px/1.4 system-ui, sans-serif; color: #ececec; background: #2f2f2f;
          border: 1px solid #4a4a4a; border-radius: 12px; padding: 10px 12px;
          box-shadow: 0 6px 24px rgba(0,0,0,.4); max-height: 40vh; overflow: auto; }
  .head { display: flex; justify-content: space-between; align-items: center;
          font-size: 12px; color: #9b9b9b; margin-bottom: 6px; }
  .x { background: none; border: 0; color: #9b9b9b; cursor: pointer; font-size: 16px; }
  .item { background: #212121; border: 1px solid #3c3c3c; border-radius: 8px;
          padding: 8px 10px; margin-top: 6px; cursor: pointer; white-space: pre-wrap; }
  .item:hover { border-color: #6b8afd; }
`;

let host: HTMLDivElement | null = null;
let cleanup: (() => void) | null = null;

export function hideCard() {
  cleanup?.();
  cleanup = null;
  host?.remove();
  host = null;
}

export function isCardVisible(): boolean {
  return host !== null;
}

export function showCard(anchor: HTMLElement, opts: CardOptions) {
  hideCard();

  const el = document.createElement("div");
  const root = el.attachShadow({ mode: "open" });

  const style = document.createElement("style");
  style.textContent = STYLE;

  const card = document.createElement("div");
  card.className = "card";

  const head = document.createElement("div");
  head.className = "head";
  const title = document.createElement("span");
  title.textContent = "Suggested rewrite. Click to use.";
  const close = document.createElement("button");
  close.className = "x";
  close.textContent = "×";
  close.setAttribute("aria-label", "Dismiss");
  close.addEventListener("click", () => opts.onDismiss());
  head.append(title, close);
  card.append(head);

  for (const text of opts.suggestions) {
    const item = document.createElement("div");
    item.className = "item";
    item.textContent = text; // textContent, never innerHTML: the text comes from an LLM
    item.addEventListener("click", () => opts.onAccept(text));
    card.append(item);
  }

  root.append(style, card);
  el.style.cssText = "position:fixed;z-index:2147483647;";
  document.body.append(el);
  host = el;

  const place = () => {
    const rect = anchor.getBoundingClientRect();
    const h = el.offsetHeight;
    const below = rect.bottom + 8;
    // ChatGPT's box sits at the bottom of the viewport, so flip above if there's no room.
    const top = below + h > window.innerHeight ? Math.max(8, rect.top - h - 8) : below;
    el.style.left = `${rect.left}px`;
    el.style.width = `${rect.width}px`;
    el.style.top = `${top}px`;
  };
  place();
  window.addEventListener("resize", place);
  window.addEventListener("scroll", place, true);
  cleanup = () => {
    window.removeEventListener("resize", place);
    window.removeEventListener("scroll", place, true);
  };
}
