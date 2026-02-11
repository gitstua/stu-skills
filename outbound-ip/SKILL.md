---
name: outbound-ip
description: Get the current public/outbound IP address of this machine using a reliable shell workflow with multiple fallback endpoints. Use when users ask for outbound IP, public IP, WAN IP, egress IP, or need IP checks before firewall/network allowlisting.
license: GPL-3.0-only
---

# Outbound IP

Use `scripts/get_outbound_ip.sh` for deterministic public IP lookup with endpoint fallback.

## Workflow

1. Run the helper script:
   - `scripts/get_outbound_ip.sh`
2. Return the resulting IPv4/IPv6 value exactly as printed.

## Notes

- The script tries several HTTPS endpoints and returns the first valid IP.
- Use `--family 4` to force IPv4 and `--family 6` to force IPv6.
- Use `--json` when downstream automation needs structured output.
- If all providers fail, report the error and likely network/DNS restrictions.
