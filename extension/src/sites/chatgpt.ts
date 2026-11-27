// Everything that depends on ChatGPT's page layout lives in this file, so supporting another
// site means writing one more file like this.

// Where ChatGPT's message box may be: the first selector that finds an element wins
const INPUT_SELECTORS = [
  "#prompt-textarea",
  'div[contenteditable="true"][role="textbox"]',
];

export function findInput(): HTMLElement | null {
  for (const selector of INPUT_SELECTORS) {
    const el = document.querySelector<HTMLElement>(selector);
    if (el) {
      return el;
    }
  }
  return null;
}

/** The text currently typed in the box (a <textarea> has .value; an editable div has .innerText). */
export function readDraft(el: HTMLElement): string {
  if (el instanceof HTMLTextAreaElement) {
    return el.value;
  }
  return el.innerText;
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
