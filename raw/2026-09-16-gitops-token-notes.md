# Notes: API tokens on the GitOps server (2026-09-16)

Source: a debugging session, copied as written. Do not edit.

- `generate-token --account <sso user>` answers `account does not exist`.
- `get-user-info` shows the same user as logged in.
- The server stores API keys only for local accounts with the apiKey capability.
- SSO identities come through the identity broker and are not accounts.
- The SSO session token lives 24 hours; the CLI renews it with a refresh token.
- A local account `readonly-bot` with get-only permissions exists in prod and test.
