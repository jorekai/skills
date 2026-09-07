#!/usr/bin/env bash
# The gate before every commit: STYLE.md rules a script can check, private data, then every offline test.
# Exit 1 with one line per hit; prints ok when everything passes.
#   scripts/check.sh            style and private data, then tests
#   scripts/check.sh --no-tests style and private data only
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
hit() { echo "$1"; fail=1; }

files=$(git ls-files | grep -v 'scripts/check.sh$')

# Private data: analytics ids, IndexNow key files, server paths, tracked workspaces and links. Customer names
# and domains come from .check_public.local (gitignored, one regex per line) so this script never names them.
private='G-[A-Z0-9]{8,}|[a-f0-9]{32}\.txt|/opt/plesk|--allow-root|ssh_host: [^(]'
patterns=0
if [[ -f .check_public.local ]]; then
  while IFS= read -r pat; do
    [[ -n "$pat" ]] || continue
    private="$private|$pat"; patterns=$((patterns + 1))
  done < .check_public.local
fi
(( patterns )) || echo "warning: no customer patterns (.check_public.local is missing or empty), only generic private-data checks run" >&2
while IFS= read -r line; do hit "private: $line"; done < <(echo "$files" | xargs grep -nE "$private" 2>/dev/null)
while IFS= read -r line; do hit "home path: $line"; done < <(echo "$files" | xargs grep -nE "/(Users|home)/[a-z][a-z0-9_-]+/" 2>/dev/null)
while IFS= read -r f; do hit "workspace tracked: $f"; done < <(echo "$files" | grep -E '^docs/')
while IFS= read -r f; do hit "link tracked: $f"; done < <(echo "$files" | grep -E '^\.(agents|claude)/skills/')

# Style (STYLE.md, "Forbidden"): em dashes, arrows, filler words, emoji. STYLE.md names them and is exempt.
style=$(echo "$files" | grep -v "^STYLE.md$")
while IFS= read -r line; do hit "dash: $line"; done < <(echo "$style" | xargs grep -n "—" 2>/dev/null)
while IFS= read -r line; do hit "arrow: $line"; done < <(echo "$style" | grep -vE '\.(py|sh|json|yaml|yml)$' | xargs grep -nE "→|[[:space:]]->[[:space:]]|[[:space:]]=>[[:space:]]" 2>/dev/null | grep -vE '^[^:]+:[0-9]+:\s*[A-Za-z0-9_"\[\]]+ *(-->|-\.|==)' )
while IFS= read -r line; do hit "en dash: $line"; done < <(echo "$style" | xargs perl -CSD -ne '
  $c = $_; $c =~ s/[\d}]\s*\x{2013}\s*[\d{]//g;
  $c =~ s/(?:Crawled|Discovered) \x{2013} currently not indexed//g;
  print "$ARGV:$.:$_" if $c =~ /\x{2013}/; close ARGV if eof' 2>/dev/null)
filler='\b(delve|leverage|seamless(ly)?|robust|crucial|game-changer|unlock|in today.s|it.s worth noting|here.s the thing|let that sink in)\b'
while IFS= read -r line; do hit "filler: $line"; done < <(echo "$style" | xargs grep -niE "$filler" 2>/dev/null)
while IFS= read -r line; do hit "emoji: $line"; done < <(echo "$style" | xargs perl -CSD -ne 'print "$ARGV:$.:$_" if /[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]/; close ARGV if eof' 2>/dev/null)

# Every plugin's version equals the top entry of the changelog beside its manifest; a version
# bump without a changelog line is a hit. One version and one changelog per plugin (decisions/0013).
while IFS= read -r manifest; do
  dir=$(dirname "$(dirname "$manifest")"); [[ "$dir" == "." ]] && log="CHANGELOG.md" || log="$dir/CHANGELOG.md"
  [[ -f "$log" ]] || { hit "changelog: $manifest has no $log beside it"; continue; }
  pv=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$manifest")
  cv=$(grep -m1 -oE '^## [0-9]+\.[0-9]+\.[0-9]+' "$log" | cut -c4-)
  [[ "$pv" == "$cv" ]] || hit "version: $manifest says $pv, $log top entry says $cv"
done < <(git ls-files '*.claude-plugin/plugin.json')

# The router must not lie: every skill directory is named in its theme's router and in README.md,
# and every jorekai-<theme>:<name> written anywhere resolves to a directory. CHANGELOG.md and
# decisions/ are history and may name a skill that is gone.
for d in $(git ls-files 'skills/*/*/SKILL.md' | xargs -n1 dirname); do
  theme=$(basename "$(dirname "$d")"); name=$(basename "$d")
  [[ "$name" == "$theme" ]] && continue      # the theme's router names the others, not itself
  grep -q "jorekai-$theme:$name\`" "skills/$theme/$theme/SKILL.md" || hit "router: jorekai-$theme:$name missing in skills/$theme/$theme/SKILL.md"
  grep -q "jorekai-$theme:$name\`" README.md || hit "readme: jorekai-$theme:$name missing in README.md"
done
while IFS= read -r ref; do
  [[ -d "skills/${ref%%:*}/${ref#*:}" ]] || hit "stale reference: jorekai-$ref names no skill directory"
done < <(git ls-files '*.md' | grep -vE '^(CHANGELOG\.md|decisions/)' | xargs grep -ohE 'jorekai-[a-z]+:[a-z-]+' | sed 's/^jorekai-//' | sort -u)

# A skill is user-invoked or the agent may reach it, and the two files that say so must agree.
# One of them drifting is how a skill silently changes who can start it.
for d in $(git ls-files 'skills/*/*/SKILL.md' | xargs -n1 dirname); do
  yaml="$d/agents/openai.yaml"
  if grep -q '^disable-model-invocation: true' "$d/SKILL.md"; then
    grep -q 'allow_implicit_invocation: false' "$yaml" \
      || hit "invocation: $d/SKILL.md is user-invoked, $yaml does not refuse implicit invocation"
  elif grep -q 'allow_implicit_invocation: false' "$yaml"; then
    hit "invocation: $yaml refuses implicit invocation, $d/SKILL.md does not say so"
  fi
done

# Every check id a script emits has a row in its theme's fixes table. A finding whose id nobody
# explains cannot be acted on, and an id that outlives its check is how the table starts lying.
for fixes in $(git ls-files 'skills/*/*/references/fixes.md'); do
  theme=$(echo "$fixes" | cut -d/ -f2)
  # Only the theme's own router table is the contract; a sub-skill may keep fixes of its own.
  [[ "$fixes" == "skills/$theme/$theme/references/fixes.md" ]] || continue
  # The namespaces come from the table itself, not from a list in this script. A hard-coded list
  # lets every id of a new namespace escape this gate in silence, which is how the table starts
  # lying: the check exists to catch an id nobody explains.
  ns=$(grep -ohE '^\| `[a-z]+\.[a-z][a-z-]*`' "$fixes" | sed 's/.*`\([a-z]*\)\..*/\1/' | sort -u | paste -sd'|' -)
  [[ -n "$ns" ]] || { hit "fixes: $fixes names no check id, so nothing can be checked against it"; continue; }
  while IFS= read -r id; do
    [[ -n "$id" ]] || continue
    grep -q "| \`$id\`" "$fixes" || hit "fixes: check id $id has no row in $fixes"
  done < <(git ls-files "skills/$theme/*/scripts/*.py" | grep -v '/test_' \
             | xargs grep -ohE "\"($ns)\.[a-z][a-z-]*\"" 2>/dev/null | tr -d '"' | sort -u)
done

# Every unit a script measures in is the unit its fixes row names, written as (`unit`) at the end
# of the measure column. A row graded against a number in another unit is graded against nothing.
for fixes in $(git ls-files 'skills/*/*/references/fixes.md'); do
  theme=$(echo "$fixes" | cut -d/ -f2)
  [[ "$fixes" == "skills/$theme/$theme/references/fixes.md" ]] || continue
  while IFS= read -r script; do
    while read -r id unit; do
      [[ -n "$id" && -n "$unit" ]] || continue
      row=$(grep -m1 "| \`$id\`" "$fixes")
      [[ "$row" == *"(\`$unit\`)"* ]] || hit "unit: $script measures $id in $unit, $fixes does not say so"
    done < <(python3 "$script" --measures 2>/dev/null)
  done < <(git ls-files "skills/$theme/*/scripts/*.py" | grep -v '/test_')
done

# Sources older than 180 days are a warning, not a hit: refresh them when touching the skill.
python3 scripts/sources_age.py --days 180 | sed 's/^/warning: stale source: /' | grep -v ': 0 row' >&2

# Secret scan over the whole history when gitleaks is installed (CI always runs it).
if command -v gitleaks >/dev/null; then
  gitleaks git . --no-banner --redact --exit-code 1 >/dev/null 2>&1 && echo "pass: gitleaks" || hit "gitleaks found a secret: run gitleaks git . --redact"
else
  echo "warning: gitleaks not installed, secret scan skipped (brew install gitleaks)" >&2
fi

(( fail )) && exit 1
[[ "${1:-}" == "--no-tests" ]] && { echo ok; exit 0; }

# Offline tests and syntax checks, one per script that a SKILL.md calls.
t() { "$@" >/dev/null 2>&1 && echo "pass: $*" || { echo "FAIL: $*"; fail=1; }; }
t python3 skills/seo/tech-audit/scripts/test_audit.py
t python3 skills/seo/gsc-review/scripts/test_gsc.py
t python3 skills/seo/and-now/scripts/test_status.py
t python3 skills/seo/setup/scripts/test_scaffold.py
t python3 skills/seo/gsc-review/scripts/gsc_opportunities.py --help
t python3 skills/seo/gsc-review/scripts/snippets.py --help
t python3 skills/seo/setup/scripts/scaffold.py --root "$(mktemp -d)/docs/seo" example.com
t python3 skills/seo/tech-audit/scripts/audit.py --help
t python3 skills/seo/and-now/scripts/status.py --help
t python3 skills/dx/setup/scripts/test_scaffold.py
t python3 skills/dx/and-now/scripts/test_status.py
t python3 skills/dx/setup/scripts/scaffold.py --root "$(mktemp -d)/dx" example-machine
t python3 skills/dx/setup/scripts/scaffold.py --help
t python3 skills/dx/and-now/scripts/status.py --help
t python3 skills/dx/repos/scripts/test_repos.py
t python3 skills/dx/machine/scripts/test_machine.py
t python3 skills/dx/repos/scripts/repos.py --help
t python3 skills/dx/machine/scripts/machine.py --help
t python3 skills/dx/grade/scripts/test_grade.py
t python3 skills/dx/grade/scripts/grade.py --help
t python3 skills/dx/friction/scripts/test_friction.py
t python3 skills/dx/friction/scripts/friction.py --help
t python3 skills/ops/setup/scripts/test_scaffold.py
t python3 skills/ops/and-now/scripts/test_status.py
t python3 skills/ops/access/scripts/test_access.py
t python3 skills/ops/availability/scripts/test_availability.py
t python3 skills/ops/setup/scripts/scaffold.py --root "$(mktemp -d)/dx" example-host
t python3 skills/ops/setup/scripts/scaffold.py --help
t python3 skills/ops/and-now/scripts/status.py --help
t python3 skills/ops/access/scripts/access.py --help
t python3 skills/ops/availability/scripts/availability.py --help
t python3 skills/ops/grade/scripts/test_grade.py
t python3 skills/ops/grade/scripts/grade.py --help
t python3 skills/ops/grade/scripts/grade.py --namespaces
t bash -n skills/ops/setup/scripts/remote.sh
t bash -n skills/seo/connect/templates/wizard.sh
t bash -n skills/seo/connect/scripts/indexnow.sh
t bash -n scripts/link.sh
# A filter that matches nothing must reach the message, not die on an empty array under `set -u`.
t bash -c 'bash scripts/link.sh "$(mktemp -d)" nosuchskill 2>&1 | grep -qx "nothing matched"'
t python3 scripts/sources_age.py --help
for f in $(git ls-files 'skills/*/*/agents/openai.yaml'); do t test -s "$f"; done
for d in $(git ls-files 'skills/*/*/SKILL.md' | xargs -n1 dirname); do t test -f "$d/agents/openai.yaml"; done

(( fail )) && exit 1
echo ok
