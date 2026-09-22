// Every file the generator owns, against the hash it was written with. A change made by hand
// goes into the generator's input and is regenerated, or the file is taken over with --disown.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

// Every owned file against its hash: the ones that moved and the ones that are gone.
function compare(root, files, disowned) {
  const changed = [];
  const missing = [];
  for (const [file, hash] of Object.entries(files)) {
    if (disowned.has(file)) continue;
    const full = join(root, file);
    if (!existsSync(full)) {
      missing.push(file);
      continue;
    }
    const now = createHash("sha256").update(readFileSync(full)).digest("hex");
    if (now !== hash) changed.push(file);
  }
  return { changed, missing };
}

// The manifest as the two things this pass reads from it: the owned files with their hashes, and
// the paths a person took over.
function read(path) {
  const manifest = JSON.parse(readFileSync(path, "utf8"));
  return { files: manifest.files ?? {}, disowned: new Set(manifest.disowned ?? []) };
}

function say(line) {
  process.stdout.write(line);
}

function main() {
  const root = process.cwd();
  const path = join(root, ".stack", "generated.json");
  if (!existsSync(path)) {
    say(
      "failed  drift  no .stack/generated.json; allowed: the manifest jorekai-stack:new writes\n",
    );
    process.exit(1);
  }
  const { files, disowned } = read(path);
  const { changed, missing } = compare(root, files, disowned);
  for (const f of changed) {
    say(`${f}  decl.generated  changed by hand; allowed: regenerate it, or --disown it\n`);
  }
  for (const f of missing) {
    say(`${f}  decl.generated  missing; allowed: regenerate it, or --disown it\n`);
  }
  if (changed.length || missing.length) process.exit(1);
  say(`ok  drift  ${Object.keys(files).length - disowned.size} generated file(s) unchanged\n`);
}

main();
