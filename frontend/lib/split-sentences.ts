/**
 * Splits a whole answer into sentences for the hover link between answer and
 * map. Temporary: once answers stream, the backend releases them a sentence at
 * a time and this goes away. Text keeps its markdown, so each unit can still be
 * rendered with `react-markdown`.
 */

const ABBREVIATIONS = new Set(["u.s.", "inc.", "corp.", "co.", "ltd.", "vs.", "e.g.", "i.e."]);
const LIST_ITEM = /^(?:[-*+]|\d+\.)\s/;
const ENDING = /[.!?]/;
const CLOSING_MARKERS = /^[*_"')\]]*/;
const NEXT_SENTENCE_START = /^[A-Z0-9$"'(*_[]/;

export function splitSentences(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => (LIST_ITEM.test(line) ? [line] : splitLine(line)));
}

function splitLine(line: string): string[] {
  const sentences: string[] = [];
  let start = 0;

  for (let index = 0; index < line.length; index++) {
    if (!ENDING.test(line[index])) continue;

    const end = index + 1 + (line.slice(index + 1).match(CLOSING_MARKERS)?.[0].length ?? 0);
    const after = line.slice(end);
    if (!/^\s/.test(after) || !NEXT_SENTENCE_START.test(after.trimStart())) continue;

    const sentence = line.slice(start, end);
    if (endsWithAbbreviation(line.slice(start, index + 1)) || hasOpenBold(sentence)) continue;

    sentences.push(sentence);
    start = end + after.length - after.trimStart().length;
    index = start - 1;
  }

  const rest = line.slice(start);
  return rest ? [...sentences, rest] : sentences;
}

function endsWithAbbreviation(text: string): boolean {
  const lastWord = text.split(/\s+/).at(-1)?.toLowerCase().replace(/^[*_"'(]+/, "");
  return lastWord !== undefined && ABBREVIATIONS.has(lastWord);
}

function hasOpenBold(text: string): boolean {
  return (text.match(/\*\*/g)?.length ?? 0) % 2 === 1;
}
