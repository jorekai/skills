# Tools

Interchangeable. A step never names one; it names what has to be true. This file says what each is for, so a session that carries a different one is not blocked.

| For | What it takes | Notes |
|---|---|---|
| The map | `python3 scripts/catalog.py` | Stdlib, no network. Reads the shipped snapshot, or a checkout with `--scan`. |
| A page the user can open and keep | A way for this session to publish an HTML file and return a link | Claude Code publishes an artifact. A session with no such way prints the tables instead, which is the same content. |
| A diagram of a loop | HTML and CSS in the page itself | No diagram library and no external file. A page that needs a script from elsewhere shows nothing when that host is blocked. |
| The same map in another agent | `scripts/link.sh <repo> intro` | Codex reads a skill from a folder in the repository, so the link is what makes it visible there. |

The page and the answer in the terminal carry the same rows. The page is worth publishing when the user keeps it or shares it; a person who asked one question about one theme is answered faster in the terminal.
