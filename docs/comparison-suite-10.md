# Terminal-Bench 2.0 comparison suite

This fixed public task set is used for matched Codex, Claude Code, and
mini-swe-agent comparisons. The task list is identical in every agent
configuration; only the agent runner and its required provider credential
change.

| Task | Difficulty | Category |
| --- | --- | --- |
| `fix-git` | easy | software-engineering |
| `cobol-modernization` | easy | software-engineering |
| `regex-log` | medium | data-processing |
| `sanitize-git-repo` | medium | security |
| `break-filter-js-from-html` | medium | security |
| `kv-store-grpc` | medium | software-engineering |
| `qemu-startup` | medium | system-administration |
| `raman-fitting` | medium | scientific-computing |
| `fix-code-vulnerability` | hard | security |
| `gpt2-codegolf` | hard | software-engineering |

Each agent runs one attempt per task, sequentially, with no automatic retries.
The comparison reports execution completion separately from benchmark score:
an agent can finish a task but receive a failing benchmark score.

The configuration's cost ceiling is a declared planning boundary. It is not a
provider billing guarantee; observed cost comes from Harbor's completed job
metadata.
