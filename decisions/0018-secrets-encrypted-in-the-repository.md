# 0018: Secrets live encrypted in the repository

## Context

The secrets a deployed service needs were copied to the host by hand, from one workstation. What is
on the host is the only record that they exist, in which order they were placed, and which of them
is still missing. A second host, or the same host after a rebuild, is a memory exercise.

The alternatives each cost something. An external store means the host depends on a third service
at the moment it rolls out. A folder on one disk means the truth lives on exactly one machine.

## Decision

Secrets live encrypted in the private repository that already holds the deployment. The plaintext
never leaves the encryption tool, the key material sits on the host, and the deploy step decrypts
into the path, owner and mode a template names.

`recovery.py` measures what that leaves behind: `secret.missing` for a required secret that is
absent, `secret.plaintext` for a secret outside the permitted store, `secret.in-repo` for an
unencrypted one inside a repository on the host, and `secret.mode` for owner or mode above the bar.

## Consequences

One tool more in the chain, and a key on the host that itself has to be placed by hand once. That
one placement is the whole manual surface; everything after it is in the repository and versioned.

The choice between the two common tools is deliberately left open until the deploy skill is built,
because it depends on what the host already carries.
