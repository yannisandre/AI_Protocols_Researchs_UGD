#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export LAB_UID="$(id -u)" LAB_GID="$(id -g)"

compose() {
  if [ -n "${LAB_ENV_FILE:-}" ]; then
    docker compose --env-file "$LAB_ENV_FILE" "$@"
  else
    docker compose "$@"
  fi
}

setup() {
  compose build proxy
  mkdir -p .local results
  docker run --rm --network none --user "$LAB_UID:$LAB_GID" \
    --mount "type=bind,src=$PWD,dst=/workspace" \
    mcp-proxy-s1:0.1.0 python scripts/prepare.py /workspace
}
start() {
  if [ ! -f .local/ready ]; then setup; fi
  compose up -d --wait collector mcp-server proxy
}

action="${1:-help}"
if [ "$#" -gt 0 ]; then shift; fi
case "$action" in
  setup) setup ;;
  up) start ;;
  test)
    setup
    compose --profile test run --rm --no-deps tests
    start
    compose --profile run run --rm agent python -m lab.agent --driver scripted --suite
    compose --profile run run --rm agent python -m lab.agent --driver scripted --scenario content --suite
    compose --profile run run --rm agent python -m lab.agent --driver scripted --scenario content --guard dlp --suite
    ;;
  run)
    start
    compose --profile run run --rm agent python -m lab.agent "$@"
    ;;
  evaluate)
    start
    compose --profile run run --rm agent python -m lab.evaluate_v2 "$@"
    ;;
  codex)
    export CODEX_BINARY="$(readlink -f "${CODEX_BINARY:-$(command -v codex)}")"
    export CODEX_CODE_MODE_HOST="${CODEX_CODE_MODE_HOST:-$(dirname "$CODEX_BINARY")/codex-code-mode-host}"
    export CODEX_AUTH_FILE="${CODEX_AUTH_FILE:-${CODEX_HOME:-$HOME/.codex}/auth.json}"
    if [ ! -x "$CODEX_BINARY" ] || [ ! -x "$CODEX_CODE_MODE_HOST" ] || [ ! -f "$CODEX_AUTH_FILE" ]; then
      echo 'Install the Linux Codex CLI with its matching code-mode host and sign in with ChatGPT first.' >&2
      exit 1
    fi
    start
    compose -f compose.yaml -f compose.codex.yaml run --rm codex python -m lab.codex_agent "$@"
    ;;
  down) compose down --remove-orphans ;;
  logs) compose logs --tail 80 "$@" ;;
  *)
    cat <<'HELP'
./lab.sh setup                 Build the pinned image and prepare local credentials
./lab.sh test                  Unit checks + fifteen scripted controls, including DLP (no API key)
./lab.sh run --driver llm --mode baseline --variant attack
./lab.sh run --driver llm --suite --repeats 3
LAB_ENV_FILE=.env.openai ./lab.sh run --driver llm --scenario content --suite
LAB_ENV_FILE=.env.openai ./lab.sh run --driver llm --scenario content --compare-guards
LAB_ENV_FILE=.env.guards.openai ./lab.sh evaluate --campaign recovery-v2-new-openai
LAB_ENV_FILE=.env.anthropic ./lab.sh run --preflight
./lab.sh codex --probe         Probe the local Codex MCP client without a model turn
./lab.sh codex --suite         Real Codex turns using your ChatGPT subscription
./lab.sh down                  Stop only this lab; retain local evidence
HELP
    ;;
esac
