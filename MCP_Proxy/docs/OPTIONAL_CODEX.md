# Optional Codex integration

Commands are run from `MCP_Proxy/`. This integration is retained for the historical
observations discussed in Section 6; it is not part of the 96-run v2 dataset.

## Codex experiment using a ChatGPT subscription
This optional historical integration tests the complete Codex host/model combination.
The main paper evaluation uses the minimal API driver instead. This path needs a supported ChatGPT login and uses that subscription's
Codex allowance, not `LLM_API_KEY` or API credits.

On Linux, install Codex and its matching `codex-code-mode-host` executable, then sign in normally
with `codex login`. `lab.sh` discovers the resolved binary and its sibling helper; override
`CODEX_BINARY` and `CODEX_CODE_MODE_HOST` if needed. The tested desktop distribution provides both
under `/usr/lib/chatgpt/resources/`. A file-backed ChatGPT login must exist at
`$CODEX_HOME/auth.json` (default `~/.codex/auth.json`); `CODEX_AUTH_FILE` can select another file.
Keyring-only authentication is not adapted automatically by this first runner.

```bash
./lab.sh setup
./lab.sh codex --probe                  # Discovery only; no model turn
./lab.sh codex --mode baseline --variant clean
./lab.sh codex --mode baseline --variant attack
./lab.sh codex --mode enforce --variant attack
./lab.sh codex --suite                  # Six real model turns, including benign/export controls
```

The optional `compose.codex.yaml` runs Codex in a dedicated container with an empty temporary
workspace/home. It mounts only the two executables, a read-only source authentication file, the lab CA,
the host-control token and the output directory. It does not mount the repository, document fixtures,
other host files or your Codex configuration. The authentication file is linked into the temporary
home, never copied into an image or a report. The runner checks that the access token remains valid
past its turn deadline and refuses expiring sessions rather than attempting a refresh in the lab.
Refresh/sign in normally on the host if instructed. The source credential mount is read-only.

Shell, image, browser, web search, plugins, other MCP servers, memory and subagent features are disabled
for the run. The internal code-mode host is retained because this Codex version requires it to dispatch
MCP tools even with code mode disabled. Tool activity outside the three laboratory tools invalidates
the run. The container has model-provider Internet access but no direct route to the MCP server or
collector; all MCP actions use the proxy. No host port is published.

`mcp_2026_07_28` is explicitly enabled for this process only. The runner first checks discovery of
all three tools. It then sends the user's task through `turn/start` and waits for completion; it never
uses `mcpServer/tool/call` to manufacture a sequence. Baseline and enforced runs use the same Codex
instructions and tool set. No human approvals are solicited for these preauthorized synthetic tools.
The proxy policy still comes from the trusted host, not from the document or the model.

The default model reported by `model/list` is selected once per invocation and recorded; use `--model`
to fix a model explicitly for later repetitions. `--timeout` bounds each turn (180 seconds by default).
The runner stops its campaign on an execution error, preserving all attempted runs. A model's refusal
to follow an injection or failure to create a draft is retained as an observed outcome, not silently
replaced with scripted behavior.

Results appear in `results/codex_<run_id>/report.json`, alongside `codex-control.jsonl` and a stderr
log. Reports include the effective/requested model, Codex version, both binary hashes, disabled features,
model-turn status, token usage where reported, proxy exchanges and independent effects/receipt logs.
`proxy_llm_requests` is zero for Codex: inference goes directly from Codex to its provider and the
proxy does not observe Codex's model prompts. Do not interpret that counter as absence of inference.

`--probe` reports are explicitly labelled **no model turn**. Legacy Codex clients are not translated
automatically. A refused or failed connection does not establish injection resistance. For research,
record the exact Codex build and feature flag: this is a host/model experiment, not an isolated test
of the underlying model. The public API driver remains useful for separating those factors.

The first complete campaign (30 October 2026) used `codex-cli 0.162.0-alpha.17.2` and the reported
default model `gpt-6.1-sol`. All six tasks produced a draft and both explicitly authorized exports
reached the collector. In both attacked runs, Codex avoided B and did not attempt an export, including
with policy enforcement disabled. Consequently, no extra protection from the proxy can be attributed
to these two samples. Scripted adversarial controls separately verify that the proxy blocks forbidden
calls. See the reference results for counts, limits and reproducibility details.
