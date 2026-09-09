# Tools

What each tool is for, and what this theme does when it is not installed. Every measuring pass runs without any of them: the tool raises the coverage, it never gates the pass. A missing tool is a note with the install command and no measure, because a zero nobody measured would settle a log row.

| Tool | What it adds | Without it |
|---|---|---|
| A secret scanner with provider rules | Provider-specific patterns and a history walk that is faster than reading every patch | `jorekai-security:secrets` uses its own provider prefixes and entropy over the tracked files, and over the history when it is asked for it |
| A dependency scanner reading the vulnerability database | Ecosystem coverage and transitive resolution for lock formats this theme parses only in part | `jorekai-security:deps` parses the lock files it knows and asks the database over HTTP, or reads the cache |
| A pattern-based static analyser | Rule packs per language, which find classes of sink this theme's rules were never written for | `jorekai-security:review` reads the code and writes its own rules, which is what the loop grades anyway |
| The forge's command line client | The commit sha behind a tag, and the advisory list the forge already holds | Pinning is looked up by hand, and the forge's list stays with `jorekai-dx:github` |

The catalogues a pass downloads are files, not services: the advisory database, the list of exploited flaws, and the exploitation-probability table. Each is cached under `cache/` in the workspace with the date it was fetched, so a pass runs on a train and says how old its answer is.

Rules for this file, and for whoever adds a row: a tool is interchangeable, so no step in any `SKILL.md` names one. The name lives here, the behaviour lives in the script, and the script degrades to its own reading when the name is not on the machine.
