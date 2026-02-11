#!/usr/bin/env bash
set -euo pipefail

family="any"
json=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --family)
      shift
      [[ $# -gt 0 ]] || { echo "missing value for --family (use 4 or 6)" >&2; exit 2; }
      case "$1" in
        4|6) family="$1" ;;
        *) echo "invalid --family value: $1 (use 4 or 6)" >&2; exit 2 ;;
      esac
      ;;
    --json)
      json=1
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: get_outbound_ip.sh [--family 4|6] [--json]

Options:
  --family 4|6   Force IPv4 or IPv6 lookup.
  --json         Print JSON: {"ip":"...","family":"IPv4|IPv6","source":"..."}
USAGE
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

providers=(
  "https://api64.ipify.org"
  "https://ifconfig.me/ip"
  "https://checkip.amazonaws.com"
)

curl_flags=(--fail --silent --show-error --connect-timeout 4 --max-time 8)
if [[ "$family" == "4" ]]; then
  curl_flags+=(--ipv4)
elif [[ "$family" == "6" ]]; then
  curl_flags+=(--ipv6)
fi

is_ipv4() {
  local ip="$1"
  [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
  IFS='.' read -r a b c d <<< "$ip"
  for octet in "$a" "$b" "$c" "$d"; do
    (( octet >= 0 && octet <= 255 )) || return 1
  done
}

is_ipv6() {
  local ip="$1"
  [[ "$ip" == *:* ]] || return 1
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY' "$ip" >/dev/null 2>&1
import ipaddress, sys
ipaddress.IPv6Address(sys.argv[1])
PY
  else
    [[ "$ip" =~ ^[0-9A-Fa-f:]+$ ]]
  fi
}

for url in "${providers[@]}"; do
  if ip_raw="$(curl "${curl_flags[@]}" "$url" 2>/dev/null)"; then
    ip="$(printf '%s' "$ip_raw" | tr -d '[:space:]')"

    if is_ipv4 "$ip"; then
      if [[ "$family" == "6" ]]; then
        continue
      fi
      if [[ "$json" -eq 1 ]]; then
        printf '{"ip":"%s","family":"IPv4","source":"%s"}\n' "$ip" "$url"
      else
        printf '%s\n' "$ip"
      fi
      exit 0
    fi

    if is_ipv6 "$ip"; then
      if [[ "$family" == "4" ]]; then
        continue
      fi
      if [[ "$json" -eq 1 ]]; then
        printf '{"ip":"%s","family":"IPv6","source":"%s"}\n' "$ip" "$url"
      else
        printf '%s\n' "$ip"
      fi
      exit 0
    fi
  fi
done

echo "failed to determine outbound IP from all providers" >&2
exit 1
