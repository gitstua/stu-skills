#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ntfy_send.sh [options] "message"

Options:
  --topic <name>       Topic name (default: $NTFY_DEFAULT_TOPIC)
  --server <url>       Server URL (default: $NTFY_SERVER or https://ntfy.sh)
  --title <text>       Notification title
  --priority <1-5>     Priority level
  --tags <csv>         Comma-separated tags
  --token <token>      Auth token (default: $NTFY_ACCESS_TOKEN, fallback: $NTFY_TOKEN)
  --dry-run            Print curl command only
  -h, --help           Show this help
USAGE
}

TOPIC="${NTFY_DEFAULT_TOPIC:-}"
SERVER="${NTFY_SERVER:-https://ntfy.sh}"
TITLE=""
PRIORITY=""
TAGS=""
TOKEN="${NTFY_ACCESS_TOKEN:-${NTFY_TOKEN:-}}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic) TOPIC="${2:-}"; shift 2 ;;
    --server) SERVER="${2:-}"; shift 2 ;;
    --title) TITLE="${2:-}"; shift 2 ;;
    --priority) PRIORITY="${2:-}"; shift 2 ;;
    --tags) TAGS="${2:-}"; shift 2 ;;
    --token) TOKEN="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    *) break ;;
  esac
done

if [[ $# -lt 1 ]]; then
  echo "Message is required." >&2
  usage
  exit 2
fi

MESSAGE="$1"

if [[ -z "$TOPIC" ]]; then
  echo "Missing prerequisite: set NTFY_DEFAULT_TOPIC (or pass --topic)." >&2
  echo "Ask the user to provide NTFY_DEFAULT_TOPIC for this session." >&2
  exit 2
fi

if [[ -n "$PRIORITY" ]] && [[ ! "$PRIORITY" =~ ^[1-5]$ ]]; then
  echo "Priority must be an integer from 1 to 5." >&2
  exit 2
fi

URL="${SERVER%/}/${TOPIC}"

CURL_ARGS=(
  --fail-with-body
  --silent
  --show-error
  --connect-timeout 5
  --max-time 20
  --retry 2
  --retry-delay 1
  -X POST
)

if [[ -n "$TITLE" ]]; then CURL_ARGS+=( -H "Title: ${TITLE}" ); fi
if [[ -n "$PRIORITY" ]]; then CURL_ARGS+=( -H "Priority: ${PRIORITY}" ); fi
if [[ -n "$TAGS" ]]; then CURL_ARGS+=( -H "Tags: ${TAGS}" ); fi
if [[ -n "$TOKEN" ]]; then CURL_ARGS+=( -H "Authorization: Bearer ${TOKEN}" ); fi
CURL_ARGS+=( -d "$MESSAGE" "$URL" )

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'curl'
  for arg in "${CURL_ARGS[@]}"; do
    printf ' %q' "$arg"
  done
  printf '\n'
  exit 0
fi

curl "${CURL_ARGS[@]}"
echo
