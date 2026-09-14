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

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Contact

For security concerns, contact: aalok101singh@users.noreply.github.com
