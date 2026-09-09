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
# and every jorekai-<theme>:<name> written in any tracked file resolves to a directory or to a
# row under `## Planned` in that router (decisions/0021). CHANGELOG.md and decisions/ are history
# and may name a skill that is gone; a test names a fixture and not this collection, and its
# fixtures are proved by the test itself, not by a directory existing.
for d in $(git ls-files 'skills/*/*/SKILL.md' | xargs -n1 dirname); do
  theme=$(basename "$(dirname "$d")"); name=$(basename "$d")
  [[ "$name" == "$theme" ]] && continue      # the theme's router names the others, not itself
  grep -q "jorekai-$theme:$name\`" "skills/$theme/$theme/SKILL.md" || hit "router: jorekai-$theme:$name missing in skills/$theme/$theme/SKILL.md"
  grep -q "jorekai-$theme:$name\`" README.md || hit "readme: jorekai-$theme:$name missing in README.md"
done
planned=$(for router in $(git ls-files 'skills/*/*/SKILL.md'); do
  [[ "$(basename "$(dirname "$router")")" == "$(echo "$router" | cut -d/ -f2)" ]] || continue
  awk '/^## Planned/{p=1;next} /^## /{p=0} p' "$router" | grep -ohE 'jorekai-[a-z]+:[a-z-]+'
done | sed 's/^jorekai-//' | sort -u)
while IFS= read -r ref; do
  [[ -d "skills/${ref%%:*}/${ref#*:}" ]] && continue
  grep -qxF "$ref" <<<"$planned" && continue
  hit "stale reference: jorekai-$ref names no skill directory and no row under ## Planned"
done < <(git ls-files | grep -vE '(^|/)CHANGELOG\.md$|^decisions/|/test_[^/]+$' | xargs grep -ohE 'jorekai-[a-z]+:[a-z-]+' 2>/dev/null | sed 's/^jorekai-//' | sort -u)

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

# Every namespace a theme's fixes table names is graded by that theme's grade skill, and the other
# way round. A row nothing recomputes reaches its verify date and cannot be settled.
for g in $(git ls-files 'skills/*/grade/scripts/grade.py'); do
  theme=$(echo "$g" | cut -d/ -f2); fixes="skills/$theme/$theme/references/fixes.md"
  [[ -f "$fixes" ]] || continue
  owned=$(grep -ohE '^\| `[a-z]+\.[a-z][a-z-]*`' "$fixes" | sed 's/.*`\([a-z]*\)\..*/\1/' | sort -u)
  graded=$(python3 "$g" --namespaces | cut -d' ' -f1 | sort -u)
  while IFS= read -r ns; do
    [[ -n "$ns" ]] && ! grep -qxF "$ns" <<<"$graded" && hit "grade: $fixes names $ns.*, $g grades no such namespace"
  done <<<"$owned"
  while IFS= read -r ns; do
    [[ -n "$ns" ]] && ! grep -qxF "$ns" <<<"$owned" && hit "grade: $g grades $ns.*, $fixes names no id in it"
  done <<<"$graded"
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

# Colour is a hint on a report that reads the same without it (decisions/0022). A script that
# paints carries the terminal guard, and an escape reaches the output through paint() alone: one
# written anywhere else would land in a pipe, a file, and every grep in this repository.
for s in $(git ls-files 'skills/*/*/scripts/*.py' | grep -v '/test_'); do
  grep -q 'def paint(' "$s" || continue
  grep -q 'stream.isatty()' "$s" || hit "colour: $s paints without the terminal guard"
  grep -q 'NO_COLOR' "$s" || hit "colour: $s paints without honouring NO_COLOR"
done
while IFS= read -r line; do hit "colour: an escape outside paint(): $line"; done \
  < <(git ls-files 'skills/*/*/scripts/*' | grep -v '/test_' \
      | xargs grep -nF '\033[' 2>/dev/null | grep -v 'PAINT\[key\]')

# What a skill hands back has a shape too (decisions/0023). Every theme router names an answer for
# every one of its sub-skills under `## Writing the answer`, and a row that gives columns gives them
# to a skill whose SKILL.md carries the same line: the router is where the theme is read whole, the
# step is where the model reads it while working. The gate catches the omission, not the wrong choice.
bt='`'
for router in $(git ls-files 'skills/*/*/SKILL.md'); do
  theme=$(echo "$router" | cut -d/ -f2)
  [[ "$router" == "skills/$theme/$theme/SKILL.md" ]] || continue
  section=$(awk '/^## Writing the answer/{p=1;next} /^## /{p=0} p' "$router")
  [[ -n "$section" ]] || { hit "answer: $router has no ## Writing the answer section"; continue; }
  named=$(grep -oE "jorekai-$theme:[a-z-]+" <<<"$section" | sed "s/^jorekai-$theme://" | sort -u)
  for d in $(git ls-files "skills/$theme/*/SKILL.md" | xargs -n1 dirname); do
    name=$(basename "$d"); [[ "$name" == "$theme" ]] && continue
    grep -qxF "$name" <<<"$named" || hit "answer: jorekai-$theme:$name is missing from ## Writing the answer in $router"
  done
  while IFS= read -r line; do
    ans=${line#*: }
    [[ "$ans" == "$bt"* && "$ans" == *" | "* ]] || continue
    cols=$(sed "s/^$bt//; s/$bt.*//" <<<"$ans")
    for n in $(sed 's/: .*//' <<<"$line" | grep -oE "jorekai-$theme:[a-z-]+" | sed "s/^jorekai-$theme://"); do
      grep -qF "$bt$cols$bt" "skills/$theme/$n/SKILL.md" \
        || hit "answer: $router gives jorekai-$theme:$n the columns $bt$cols$bt, its SKILL.md carries no such line"
    done
  done < <(grep '^- ' <<<"$section")
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
t python3 skills/dx/report/scripts/test_report.py
t python3 skills/dx/report/scripts/report.py --help
t python3 skills/ops/setup/scripts/test_scaffold.py
t python3 skills/ops/and-now/scripts/test_status.py
t python3 skills/ops/access/scripts/test_access.py
t python3 skills/ops/availability/scripts/test_availability.py
t python3 skills/ops/recovery/scripts/test_recovery.py
t python3 skills/ops/exposure/scripts/test_exposure.py
t python3 skills/ops/setup/scripts/scaffold.py --root "$(mktemp -d)/dx" example-host
t python3 skills/ops/setup/scripts/scaffold.py --help
t python3 skills/ops/and-now/scripts/status.py --help
t python3 skills/ops/access/scripts/access.py --help
t python3 skills/ops/availability/scripts/availability.py --help
t python3 skills/ops/recovery/scripts/recovery.py --help
t python3 skills/ops/exposure/scripts/exposure.py --help
t python3 skills/ops/grade/scripts/test_grade.py
t python3 skills/ops/grade/scripts/grade.py --help
t python3 skills/ops/grade/scripts/grade.py --namespaces
t python3 skills/ops/report/scripts/test_report.py
t python3 skills/ops/report/scripts/report.py --help

t python3 skills/security/setup/scripts/test_scaffold.py
t python3 skills/security/and-now/scripts/test_status.py
t python3 skills/security/secrets/scripts/test_secrets.py
t python3 skills/security/pipeline/scripts/test_pipeline.py
t python3 skills/security/deps/scripts/test_deps.py
t python3 skills/security/review/scripts/test_review.py
t python3 skills/security/setup/scripts/scaffold.py --root "$(mktemp -d)/sec" example-repo
t python3 skills/security/setup/scripts/scaffold.py --help
t python3 skills/security/and-now/scripts/status.py --help
t python3 skills/security/secrets/scripts/secrets.py --help
t python3 skills/security/pipeline/scripts/pipeline.py --help
t python3 skills/security/deps/scripts/deps.py --help
t python3 skills/security/review/scripts/review.py --help
t python3 skills/security/grade/scripts/test_grade.py
t python3 skills/security/grade/scripts/grade.py --help
t python3 skills/security/grade/scripts/grade.py --namespaces
t python3 skills/security/report/scripts/test_report.py
t python3 skills/security/report/scripts/report.py --help
t python3 skills/intro/intro/scripts/test_catalog.py
t python3 skills/intro/intro/scripts/catalog.py --help
# The map is generated, never typed: a skill added, renamed or removed anywhere fails here
# until the snapshot knows it, the same way a router may not lie about its sub-skills.
t python3 skills/intro/intro/scripts/catalog.py --check
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
