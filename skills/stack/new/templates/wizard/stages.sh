# ─────────────────────────────────────────────────────────────────────────
# STAGES: one stage per human step. Written by jorekai-stack:new --wire.
# ─────────────────────────────────────────────────────────────────────────
# The notes go to a file the repository ignores; the date a step was done goes into stack.yaml
# under human_steps, which is what jorekai-stack:and-now reads.
CONNECTIONS="${CONNECTIONS:-.stack/wizard.md}"
STACK="${STACK:-stack.yaml}"

# mark_done "<what>": set `done: YYYY-MM-DD` on the human step whose `what` starts with the text.
mark_done() {
  local what="$1" tmp
  tmp=$(mktemp)
  awk -v w="$what" -v d="$(today)" '
    index($0, "- what: " w) == 1 { hit = 1; print; next }
    hit && $1 == "done:" { sub(/done:.*/, "done: \"" d "\""); hit = 0 }
    { print }' "$STACK" > "$tmp"
  mv "$tmp" "$STACK"
  printf '  %sdone%s %s\n' "$GREEN" "$R" "$what"
}

# One stage per port: the adapter stack.yaml names, and the two keys its account fills.
port_stage() {
  local port="$1" adapter="$2" upper
  upper=$(printf '%s' "$port" | tr '[:lower:]' '[:upper:]')
  stage "Port $port: the account behind the $adapter adapter"
  step "Create the account or the resource the $adapter adapter talks to"
  step "Put its address in ${upper}_URL and its credential in ${upper}_KEY, in the secret store, never in the repository"
  note "While both keys are empty the port runs on its memory adapter, and the gate stays green"
  if confirm "Are ${upper}_URL and ${upper}_KEY set in the secret store?"; then
    record "${upper}_SET" "$(today)"
  else
    skip "$port: set ${upper}_URL and ${upper}_KEY, then re-run"
  fi
}

ports=$(node scripts/stack-yaml.mjs --lines ports)
TOTAL_STAGES=$(( $(printf '%s\n' "$ports" | grep -c .) + 2 ))
banner "Accounts and locks for $(node scripts/stack-yaml.mjs name | tr -d '"')"

while IFS=$'\t' read -r port adapter; do
  [[ -n "$port" ]] || continue
  port_stage "$port" "$adapter"
done <<< "$ports"
if (( ${#SKIPPED[@]} == 0 )); then
  mark_done "create the accounts the wired adapters need"
fi

stage "Branch protection: the gate as the required check"
step "On the forge, protect the default branch with the check named gate as required, or run:"
note "gh api -X PUT repos/<owner>/<repo>/branches/<default>/protection -f 'required_status_checks[strict]=true' -f 'required_status_checks[contexts][]=gate' -F 'enforce_admins=true' -f 'required_pull_request_reviews[required_approving_review_count]=1' -f 'required_pull_request_reviews[require_code_owner_reviews]=true'"
step "Then add the date to stack.yaml under enforcement: gate@$(today)"
if confirm "Is the gate a required check on the default branch?"; then
  record "BRANCH_PROTECTION" "$(today)"
  mark_done "make the gate a required check"
else
  skip "branch protection: make the gate a required check, then re-run"
fi

stage "CODEOWNERS: a person who is not the agent"
step "Replace @OWNER in CODEOWNERS with a person's handle, on every line"
if confirm "Does every line of CODEOWNERS name a person?"; then
  record "CODEOWNERS" "$(today)"
  mark_done "replace the placeholder owner in CODEOWNERS"
else
  skip "CODEOWNERS: replace the placeholder, then re-run"
fi

finish
