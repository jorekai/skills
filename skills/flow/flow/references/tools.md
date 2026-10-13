# Tools

Interchangeable. A step never names one; it names what has to be true. This file says what each is for, so a session that carries a different one is not blocked.

| For | What it takes | Notes |
|---|---|---|
| The previous session | The agent's own session list, or its transcript store | Claude Code keeps one JSON lines file per session under `~/.claude/projects/`, in a folder named after the working directory. This is a heuristic, see [sources.md](sources.md). A session tool that lists sessions by folder is preferred over reading the files. |
| Background work | A task the harness runs outside the conversation and reports back from | Claude Code runs a background command or a monitor. Without one, a watch cannot start, and the answer says so. |
| A notice on the phone | A push notification tool | Optional. The notice in the conversation is always sent. |
| Pull requests and checks | The forge's command line, authenticated | `gh pr view`, `gh pr checks`, `gh pr merge`. Another forge uses its own. |
| The clipboard | `pbcopy` on macOS, `wl-copy` or `xclip` on Linux, `clip` on Windows | Read back once with `pbpaste` or its counterpart. |
| The deploy | Whatever the project documents | Never a command guessed from the stack. |
