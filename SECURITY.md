# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability within ModelHop, please send an email to the project maintainer at aalok101singh@users.noreply.github.com. All security vulnerabilities will be promptly addressed.

Please include the following information in your report:

- Type of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix and release**: Depends on severity, typically within 2 weeks

## Security Best Practices for Users

When using ModelHop:

1. **Never commit API keys** to version control
2. **Use environment variables** for API keys (via `.env` file)
3. **Rotate keys** if you suspect they've been compromised
4. **Use free tier providers** (Groq, Gemini) to minimize risk
5. **Review logs** periodically for unexpected behavior

## API Key Security

ModelHop stores API keys in:
- Environment variables (loaded from `.env`)
- Never in source code or version control

To safely use ModelHop:
```bash
# Copy the example and add your keys
cp .env.example .env
# Edit .env with your keys
# Never commit .env to git
```

## Threat Model (v1.1 agent-aware)

- **Indirect prompt injection via tool output:** queries are DATA ONLY — delimited,
  length-capped, never interpolated into control prompts (analyzer, confidence,
  consensus, judges).
- **Data exfiltration via model choice:** trust/ZDR/data-class/jurisdiction hard
  constraints filter before ranking; community sharing is k-anonymized aggregate
  cards only, never raw text or features (allowlist serializer).
- **Provenance/taint:** strict structured-output parsing (balanced-brace scanner),
  self-reported scores never trusted, fail-closed defaults with `degraded` marking.
- **Routing-state poisoning:** HMAC-signed state (`SignedStore`), hash-chained
  signed ledger with checkpoints, honest rehydration only, tamper → reset + warn.
- **Secrets:** `SecretsProvider` abstraction (env default, file/chained/AWS/Vault);
  keys never persisted, logged, or traced; `.env` parsing hardened (no eval).
- **Availability:** per-provider timeouts, bounded jittered retries, circuit
  breakers + health registry; supply chain via SBOM, SHA-pinned actions, trusted
  publishing, sigstore-signed releases.

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.1.x   | Yes       |
| 1.0.x   | Maintenance only |
| < 1.0   | No        |

## Contact

For security concerns, contact: aalok101singh@users.noreply.github.com
