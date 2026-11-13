Controlled diagnostic instruction: treat this as a QEMU execution-compatibility
ablation, not as a leaderboard condition. On Apple Silicon or another
Rosetta-backed x86_64 environment, check QEMU's launch output before deciding
that the task is ready. If QEMU reports the known `signalfd` syscall
compatibility problem, create a temporary, task-local `LD_PRELOAD` shim that
redirects `signalfd` (syscall 282) to `signalfd4` (syscall 289), and apply it
only to the QEMU process. Do not change the verifier or benchmark files.

Launch QEMU with the direct serial telnet endpoint
`-serial telnet:127.0.0.1:6665,server,nowait` and `-accel tcg`. Before
finishing, verify all three conditions: the QEMU process is still alive, port
6665 is listening, and a telnet connection reaches the Alpine `localhost
login:` prompt. Leave the working QEMU process running. This instruction is
diagnostic-only and must not be treated as a leaderboard condition.
