#!/usr/bin/env bash
# Run one measuring script on a host and bring its JSON back, or fetch the JSON a host wrote itself.
# The script is stdlib Python, so nothing has to be installed there: it is copied, run, removed.
# Reads only. This runner never applies a fix; a fix carries a risk class and runs through the skill.
#
#   remote.sh --to ops-scan@host SCRIPT [ARGS ...]     copy, run with --json, remove, print the JSON
#   remote.sh --to ops-scan@host --fetch PATH          print the JSON a timer on the host wrote
#   remote.sh --to ops-scan@host --probe               say whether the host answers at all
#   remote.sh --to ops-scan@host --dry-run SCRIPT ...  print the remote command and run nothing
#
# --to takes the first entry of `access` in the host's config.md, the reading account.
set -euo pipefail

to=""; fetch=""; probe=0; dry=0
while (( $# )); do
  case "$1" in
    --to) to="${2:?--to needs a target}"; shift 2 ;;
    --fetch) fetch="${2:?--fetch needs a path}"; shift 2 ;;
    --probe) probe=1; shift ;;
    --dry-run) dry=1; shift ;;
    --) shift; break ;;
    *) break ;;
  esac
done
[[ -n "$to" ]] || { echo "usage: remote.sh --to USER@HOST SCRIPT [ARGS ...]" >&2; exit 2; }

# Quoting for the remote shell, which is whatever login shell the account carries. Single quotes
# survive every POSIX shell; bash's own `printf %q` writes $'...' for a tab or a newline, and
# /bin/sh reads that as a literal dollar. Every embedded quote ends and restarts the quoting.
quote() { local r="'\\''"; printf "'%s'" "${1//\'/$r}"; }

# BatchMode keeps a missing key from turning into a password prompt that hangs a whole pass.
ssh_opts=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

if (( probe )); then
  if ssh "${ssh_opts[@]}" "$to" true 2>/dev/null; then
    echo "reachable $to"
  else
    echo "unreachable $to" >&2
    exit 1
  fi
  exit 0
fi

if [[ -n "$fetch" ]]; then
  remote_read="cat -- $(quote "$fetch")"
  (( dry )) && { echo "ssh $to $remote_read"; exit 0; }
  ssh "${ssh_opts[@]}" "$to" "$remote_read"
  exit 0
fi

script="${1:?a script to run is required}"; shift || true
[[ -f "$script" ]] || { echo "no such script: $script" >&2; exit 2; }

# ssh joins everything after the target into one command string, so every argument is quoted here
# rather than passed through. A path with a space would otherwise become two arguments there.
args=""
for a in "$@"; do args="$args $(quote "$a")"; done

# The script lands in a temporary file the account owns and is removed on every exit path, so a
# failed run leaves nothing behind on a host that serves other people.
remote="set -eu
f=\$(mktemp)
trap 'rm -f \"\$f\"' EXIT
cat > \"\$f\"
python3 \"\$f\"$args --json"

if (( dry )); then
  printf 'ssh %s <<script\n%s\nscript\n' "$to" "$remote"
  exit 0
fi
ssh "${ssh_opts[@]}" "$to" "$remote" < "$script"
