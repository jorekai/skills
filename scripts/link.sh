#!/usr/bin/env bash
# Link skills of this collection into a project for Codex (reads <repo>/.agents/skills/<name>/SKILL.md).
# Claude Code needs no links: the collection is a plugin (.claude-plugin/), installed once at user scope,
# and every skill is /jorekai-<theme>:<name> (see README.md, "Use in a project").
# A link is named <theme>-<skill>, the same pair as the plugin invocation jorekai-<theme>:<skill>.
# Two themes carry a skill of the same name (setup, and-now), and a bare name would let one
# overwrite the other in silence. A theme whose skill carries the theme's own name is the one
# exception: <theme> alone, because <theme>-<theme> names nothing the other spelling does not.
#   scripts/link.sh /path/to/repo               link every skill
#   scripts/link.sh /path/to/repo seo            link one bucket (skills/seo/*)
#   scripts/link.sh /path/to/repo setup ...      link named skills (globs ok)
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
repo="${1:?usage: link.sh REPO [BUCKET|SKILL ...]}"
shift || true
[[ -d "$repo" ]] || { echo "no such directory: $repo" >&2; exit 1; }

srcs=()
while IFS= read -r -d '' f; do srcs+=("$(dirname "$f")"); done < <(find "$here/skills" -name SKILL.md -print0 | sort -z)
all_srcs=("${srcs[@]}")   # the full current set, kept for pruning even when this run is scoped
if (( $# )); then
  sel=()
  for want in "$@"; do
    for s in "${srcs[@]}"; do
      bucket="$(basename "$(dirname "$s")")"; name="$(basename "$s")"
      # shellcheck disable=SC2053
      if [[ "$bucket" == "$want" || "$name" == $want ]]; then sel+=("$s"); fi
    done
  done
  # bash 3.2 (the macOS default) treats an empty array as unset under `set -u`;
  # the +expansion keeps the empty case alive so the message below is reached.
  srcs=(${sel[@]+"${sel[@]}"})
fi
(( ${#srcs[@]} )) || { echo "nothing matched" >&2; exit 1; }

# Links are relative so a clone on another machine (or a different checkout path) still resolves them.
dest="$repo/.agents/skills"
mkdir -p "$dest"
for s in "${srcs[@]}"; do
  bucket="$(basename "$(dirname "$s")")"; name="$(basename "$s")"
  if [[ "$bucket" == "$name" ]]; then link="$bucket"; else link="$bucket-$name"; fi
  rel="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$s" "$dest")"
  ln -sfn "$rel" "$dest/$link"
  echo "linked $link -> $dest/$link ($rel)"
done

# Prune what a rename or a removal left behind. A link a skill's own directory no longer earns
# stays in $dest forever otherwise, since nothing else ever revisits it. The set below is the
# full current collection, not just this run's selection, so a scoped run (one bucket, one
# skill) still cleans up a stale link from a different theme without touching a live one it
# was not asked to relink. Two things keep this from ever touching what is not ours: a plain
# file or directory is never a symlink, and a symlink whose resolved target falls outside $here
# is left alone no matter what its name is.
expected=$(for s in "${all_srcs[@]}"; do
  bucket="$(basename "$(dirname "$s")")"; name="$(basename "$s")"
  if [[ "$bucket" == "$name" ]]; then echo "$bucket"; else echo "$bucket-$name"; fi
done)
# A symlink's target comes back from realpath fully resolved (no /var-vs-/private/var
# ambiguity on macOS), so $here is resolved the same way before the two are compared.
here_real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$here")"
for path in "$dest"/*; do
  [[ -e "$path" || -L "$path" ]] || continue   # an unmatched glob with nullglob off: nothing here
  [[ -L "$path" ]] || continue                 # never a plain file or directory
  target="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$path")"
  case "$target" in
    "$here_real"/*) ;;
    *) continue ;;                             # points outside this collection: never ours to touch
  esac
  entry="$(basename "$path")"
  grep -qxF "$entry" <<<"$expected" && continue  # still names a skill that exists
  rm -f "$path"
  echo "pruned $entry (stale link into $target)"
done
