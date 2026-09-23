#!/usr/bin/env bash
# Offline tests for scripts/link.sh: linking, the theme==skill case, pruning after a rename,
# leaving a foreign symlink and a plain file alone, and a rerun changing nothing.
# Run: bash scripts/test_link.sh
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
col="$work/collection"
repo="$work/repo"
dest="$repo/.agents/skills"

fail() { echo "FAIL: $1" >&2; exit 1; }
assert_link() { [[ -L "$dest/$1" ]] || fail "$1 should be a symlink in $dest"; }
assert_absent() { [[ -e "$dest/$1" || -L "$dest/$1" ]] && fail "$1 should be gone from $dest"; return 0; }

mkdir -p "$col/skills/demo/setup" "$col/skills/demo/other" "$col/skills/demo/demo" "$repo"
echo "---" > "$col/skills/demo/setup/SKILL.md"
echo "---" > "$col/skills/demo/other/SKILL.md"
echo "---" > "$col/skills/demo/demo/SKILL.md"   # a skill carrying the theme's own name

# A copy of link.sh under test, in its own collection tree: "here" inside link.sh must be
# $col, not this repository, so pruning never reasons about the real collection.
mkdir -p "$col/scripts"
cp "$here/scripts/link.sh" "$col/scripts/link.sh"

# Basic link, including the theme==skill exception: "demo" links bare, not "demo-demo".
bash "$col/scripts/link.sh" "$repo" >/dev/null
assert_link demo
assert_link demo-setup
assert_link demo-other
[[ -e "$dest/demo-demo" ]] && fail "demo-demo should not exist, the theme's own name links bare"

# A foreign symlink and a plain file must never be touched, pruned or not.
mkdir -p "$work/outside"
echo hi > "$work/outside/thing.txt"
ln -s "$work/outside/thing.txt" "$dest/foreign-link"
echo "not a symlink" > "$dest/plain-file"

# Rerun with the same tree: idempotent, nothing pruned, nothing duplicated.
before="$(find "$dest" -maxdepth 1 | sort)"
bash "$col/scripts/link.sh" "$repo" >/dev/null
after="$(find "$dest" -maxdepth 1 | sort)"
[[ "$before" == "$after" ]] || fail "a rerun over an unchanged tree must not change $dest"
[[ -L "$dest/foreign-link" ]] || fail "a foreign symlink must survive a rerun"
[[ -f "$dest/plain-file" && ! -L "$dest/plain-file" ]] || fail "a plain file must survive a rerun"

# Rename a skill's directory: the old link is pruned, the new one appears, on a scoped run too.
mv "$col/skills/demo/other" "$col/skills/demo/renamed"
bash "$col/scripts/link.sh" "$repo" renamed >/dev/null
assert_link demo-renamed
assert_absent demo-other
assert_link demo-setup   # a scoped run still keeps what it was not asked to touch
[[ -L "$dest/foreign-link" ]] || fail "pruning must still leave a foreign symlink alone"
[[ -f "$dest/plain-file" ]] || fail "pruning must still leave a plain file alone"

# A skill removed outright is pruned even though no argument named it, because pruning reads
# the full current collection, not just this run's selection.
rm -rf "$col/skills/demo/setup"
bash "$col/scripts/link.sh" "$repo" renamed >/dev/null
assert_absent demo-setup

echo ok
