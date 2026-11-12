const INPUT_SELECTORS = [
  "#prompt-textarea",
  'div[contenteditable="true"][role="textbox"]',
];


export function findInput(): HTMLElement | null {
  for (const sel of INPUT_SELECTORS) {
    const el = document.querySelector<HTMLElement>(sel);
    if (el) return el;
  }
  return null;
}

export function readDraft(el: HTMLElement): string {
  return el instanceof HTMLTextAreaElement ? el.value : el.innerText;
}

// ChatGPT's box is a ProseMirror editor: setting innerText bypasses its state.
// execCommand goes through the browser's editing pipeline, which it does observe.
export function writeDraft(el: HTMLElement, text: string) {
  el.focus();
  if (el instanceof HTMLTextAreaElement) {
    el.value = text;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    return;
  }
  document.execCommand("selectAll", false);
  document.execCommand("insertText", false, text);
}
