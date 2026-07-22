#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv 2>/dev/null || true
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
python -m playwright install chromium 2>/dev/null || true

PROMPTS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompts-file|-PromptsFile)
      PROMPTS="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

if [[ -z "$PROMPTS" ]]; then
  echo "用法: run_batch.sh --prompts-file douyin-kepu-flow/prompts/{slug}/prompts.json" >&2
  exit 1
fi

export PYTHONPATH="$ROOT/douyin-kepu-flow"
python -m flow.run_batch --prompts-file "$PROMPTS"
