// Regex-based PII stripping. It catches structured PII (emails, phones, cards,
// API keys). It does NOT catch names or places; that needs an NER model.
// Placeholders are reversible so an accepted rewrite can be restored locally
// without the raw values ever leaving the browser.

const PATTERNS: { label: string; re: RegExp }[] = [
  { label: "EMAIL", re: /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g },
  { label: "KEY", re: /\b(?:sk|pk|ghp|xox[bp])[-_][A-Za-z0-9_-]{16,}\b/g },
  { label: "CARD", re: /\b(?:\d[ -]?){13,19}\b/g },
  { label: "PHONE", re: /\+?\d[\d\s().-]{8,}\d/g },
];

export interface StripResult {
  text: string;
  map: Record<string, string>;
}

/**
 * Replaces personal data with numbered placeholders, e.g. "bob@x.com" -> "[EMAIL_1]".
 * Returns the cleaned text and a map { "[EMAIL_1]": "bob@x.com" } to undo it later.
 */
export function stripPII(input: string): StripResult {
  const map: Record<string, string> = {};
  const counts: Record<string, number> = {}; // how many of each label we have used so far
  let text = input;

  for (const pattern of PATTERNS) {
    const label = pattern.label;
    counts[label] = 0;
    // replace() calls this function once for every match of the pattern
    text = text.replace(pattern.re, function (match) {
      counts[label] = counts[label] + 1;
      const placeholder = "[" + label + "_" + counts[label] + "]";
      map[placeholder] = match; // remember the real value, so we can put it back
      return placeholder;
    });
  }
  return { text: text, map: map };
}

/** Puts the real values back in place of the placeholders. */
export function restorePII(text: string, map: Record<string, string>): string {
  let out = text;
  for (const placeholder in map) {
    // split + join replaces EVERY occurrence (replace() with a string only does the first)
    out = out.split(placeholder).join(map[placeholder]);
  }
  return out;
}
