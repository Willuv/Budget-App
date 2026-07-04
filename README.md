# Spending Tracker

A local-first personal finance desktop app powered by Flask + PyWebView.

## Plaid Sandbox Setup

This app is configured to use Plaid's sandbox environment by default.

1. Register a Plaid developer account at https://dashboard.plaid.com/signup.
2. Create a sandbox application and copy the `client_id` and `secret`.
3. Open the app and enter your Plaid sandbox credentials on the Settings page.
4. Press Save to store the values locally. The app creates `settings.json` automatically.

> `settings.json` is ignored by `.gitignore`, so your secrets stay local and are not committed.

## Running Locally

Install the dependencies:

```powershell
pip install -r requirements.txt
```

Run the app:

```powershell
python app.py
```

## Build a standalone EXE

You can use `pyinstaller` or a similar packager to create a Windows executable.

## Security Notes

- Credentials are stored only in local `settings.json`.
- Secrets are never hardcoded in the source.
- The app uses the Plaid sandbox environment by default so you can prototype without using paid production connections.
