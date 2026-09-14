#!/usr/bin/env bash
# The one gate: every guard stack.yaml declares, in its order, cheapest first.
#   scripts/gate.sh            everything; the timing goes to .stack/gate-times.log
#   scripts/gate.sh --staged   format, lint and rules over the staged files only (the hook)
# A failure prints `failed  <guard>  <what to run and the allowed state>`. Nothing is skipped
# in silence: a tool that is not installed fails its guard and names the install command.
set -uo pipefail
cd "$(dirname "$0")/.."
mode=full
[[ "${1:-}" == "--staged" ]] && mode=staged
[[ -f stack.yaml ]] || { echo "failed  gate  no stack.yaml: run jorekai-stack:choose first"; exit 1; }
bar=$(node scripts/stack-yaml.mjs gates.gate_max_seconds 2>/dev/null || echo 0)
start=$(date +%s)
fail=0
out=$(mktemp)
trap 'rm -f "$out"' EXIT

staged=""
if [[ $mode == staged ]]; then
  staged=$(node scripts/staged.mjs)
  [[ -n "$staged" ]] || { echo "ok  gate  nothing staged"; exit 0; }
fi

# What to do when a guard fails, per guard: the command that shows the state, and the state
# that is allowed. A message that names only the ban makes an agent guess.
hint() {
  case "$1" in
    format)    echo "run pnpm exec prettier --write . ; allowed: a tree the formatter leaves unchanged" ;;
    lint)      echo "fix the lines above; allowed: functions under the bars in stack.yaml, no floating promise" ;;
    rules)     echo "fix the lines above; allowed: what each rule's message names" ;;
    waivers)   echo "fix the code, or add a waiver with reason, until and owner to stack.yaml through review" ;;
    typecheck) echo "fix the types above; allowed: strict, no suppression" ;;
    unit)      echo "fix the failing test, or cover the lines the report names; the bar is in stack.yaml" ;;
    dead)      echo "delete what nobody imports; the three bars are in stack.yaml" ;;
    drift)     echo "move the change into the generator's input and regenerate, or --disown the file" ;;
    secrets)   echo "rotate the value at the provider first, then remove the line" ;;
    browser)   echo "fix the app; allowed: / and /api/health answer 200" ;;
    *)         echo "see the output above" ;;
  esac
}

install_hint() {
  case "$1" in
    gitleaks) echo "brew install gitleaks, or the release archive named in .github/workflows/gate.yml" ;;
    node|pnpm) echo "install the runtime pinned in .nvmrc and the package manager in package.json" ;;
    *) echo "install $1" ;;
  esac
}

run() {
  local name=$1 cmd=$2 t0 t1 first
  first=${cmd%% *}
  if ! command -v "$first" >/dev/null 2>&1; then
    fail=1
    echo "failed  $name  $first is not installed: $(install_hint "$first")"
    return
  fi
  t0=$(date +%s)
  if bash -c "$cmd" >"$out" 2>&1; then
    t1=$(date +%s)
    echo "ok  $name  $((t1 - t0))s"
  else
    fail=1
    echo "failed  $name  $(hint "$name")"
    sed 's/^/    /' "$out"
  fi
}

# The guards come from the declaration, in its order. The staged mode runs the three that take a
# file list and skips the rest, because the workflow runs everything anyway.
while IFS=$'\t' read -r name cmd; do
  [[ -n "$name" ]] || continue
  if [[ $mode == staged ]]; then
    case "$name" in
      format|lint|rules) run "$name" "$cmd $(printf '%q ' $staged)" ;;
      *) continue ;;
    esac
  else
    run "$name" "$cmd"
  fi
done < <(node scripts/stack-yaml.mjs --lines guards)

end=$(date +%s)
total=$((end - start))
if [[ $mode == full ]]; then
  mkdir -p .stack
  printf '%s %s full\n' "$(date +%FT%T)" "$total" >> .stack/gate-times.log
  echo "gate took ${total}s, bar ${bar}s"
  if [[ "$bar" =~ ^[0-9]+$ ]] && (( total > bar )); then
    echo "slow  gate  ${total}s is over the bar of ${bar}s in stack.yaml; a slow gate is a gate people skip"
  fi
fi
(( fail )) && { echo "failed  gate"; exit 1; }
echo "ok  gate"
