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

export function stripPII(input: string): StripResult {
  const map: Record<string, string> = {};
  const counts: Record<string, number> = {};
  let text = input;
  for (const { label, re } of PATTERNS) {
    text = text.replace(re, (match) => {
      counts[label] = (counts[label] ?? 0) + 1;
      const placeholder = `[${label}_${counts[label]}]`;
      map[placeholder] = match;
      return placeholder;
    });
  }
  return { text, map };
}

export function restorePII(text: string, map: Record<string, string>): string {
  let out = text;
  for (const [placeholder, original] of Object.entries(map)) {
    out = out.split(placeholder).join(original);
  }
  return out;
}
