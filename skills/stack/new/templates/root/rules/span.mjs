// How far a bracket reaches: the text a block rule has to read to see whether what a call
// encloses carries what the rule requires. Counts nesting and steps over string literals the
// simple way, which is enough for a lint rule and is not a parser.
const PAIRS = { "(": ")", "{": "}", "[": "]" };

function isQuote(c) {
  return c === '"' || c === "'" || c === "`";
}

// Inside a string literal: the index after this character, and whether the literal is still open.
function inQuote(c, i, quote) {
  if (c === "\\") return [i + 1, quote];
  return [i, c === quote ? "" : quote];
}

// One character outside a literal, against the brackets still open: it opens one, closes the
// innermost one, or leaves the stack where it stands.
function nest(c, stack) {
  if (PAIRS[c]) stack.push(PAIRS[c]);
  else if (c === stack[stack.length - 1]) stack.pop();
}

// The span of the bracket that opens at or after `from`: its start and the index after its close.
export function span(text, from) {
  const open = text.slice(from).search(/[({[]/);
  if (open < 0) return [from, text.length];
  const start = from + open;
  const stack = [PAIRS[text[start]]];
  let quote = "";
  for (let i = start + 1; i < text.length; i += 1) {
    const c = text[i];
    if (quote) {
      [i, quote] = inQuote(c, i, quote);
      continue;
    }
    quote = isQuote(c) ? c : "";
    if (quote) continue;
    nest(c, stack);
    if (!stack.length) return [start, i + 1];
  }
  return [start, text.length];
}
