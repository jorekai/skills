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
