# Security policy

## Reporting

Please report vulnerabilities privately through GitHub Security Advisories. Do not include tokens,
OBS passwords, stream URLs, or production addresses in a public issue.

## Deployment boundaries

- Never expose OBS WebSocket port 4455 directly to the public internet. Use localhost, a private
  network, WireGuard, or a reverse SSH tunnel.
- Keep `config.toml` and `tokens.db` readable only by the service account (`chmod 600`).
- Use a dedicated Twitch bot account and immutable numeric IDs in the command allow-list.
- Treat `!start`, `!stop`, and `!scene` as privileged production operations.

Supported security fixes are released from the `main` branch.

