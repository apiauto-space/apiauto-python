# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem in this client or in the
apiauto.space API. Write to the support of the Telegram bot
[@apiautospace_bot](https://t.me/apiautospace_bot) instead and describe what you found and how
to reproduce it.

If your API key leaked (for example, it was committed to a repository or shipped in browser
code), report it the same way so that it can be replaced.

## Supported versions

Security fixes go into the latest release on [PyPI](https://pypi.org/project/apiauto/).

## Handling keys

The client never logs the key and masks it in `repr()`. Keep the key in the `APIAUTO_KEY`
environment variable or a secret store, and call the API from your server only: it does not
accept browser requests.
