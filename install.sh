#!/usr/bin/env bash
# One-command setup for claude-warmup-usage.
#   - creates a Python venv
#   - installs Playwright + Chromium
#   - (optionally) saves your Server酱 SendKey
#   - opens a browser so you can log into YOUR claude.ai account
#
# The login step is interactive on purpose: only you can enter your own
# credentials + 2FA. Everything else is automatic.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY="$HERE/.venv/bin/python"

say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die(){ printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 not found — install Python 3.10+ first."

say "Creating virtualenv (.venv)"
if [ ! -x "$PY" ]; then
  if python3 -m venv .venv 2>/dev/null && [ -x .venv/bin/pip ]; then
    :
  else
    echo "ensurepip unavailable; bootstrapping pip with get-pip.py ..."
    rm -rf .venv
    python3 -m venv --without-pip .venv \
      || die "venv creation failed — try: sudo apt install -y python3-venv"
    if command -v curl >/dev/null; then
      curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    else
      python3 -c "import urllib.request;urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py','/tmp/get-pip.py')"
    fi
    "$PY" /tmp/get-pip.py >/dev/null || die "pip bootstrap failed"
  fi
fi

say "Installing Python dependencies"
"$PY" -m pip install -q --upgrade pip >/dev/null
"$PY" -m pip install -q -r requirements.txt || die "pip install failed"

say "Installing Chromium for Playwright (~150 MB first time)"
if ! "$PY" -m playwright install --with-deps chromium 2>/dev/null; then
  "$PY" -m playwright install chromium || die "chromium download failed"
  echo "Note: if the browser fails to launch later, install system libs with:"
  echo "      sudo $PY -m playwright install-deps chromium"
fi

# Optional Server酱 key
if [ -z "${SERVERCHAN_KEY:-}" ] && [ ! -s "$HOME/.serverchan_key" ]; then
  say "Server酱 push notifications (optional)"
  printf 'Paste your Server酱 SendKey (or just press ENTER to skip): '
  read -r KEY || KEY=""
  if [ -n "${KEY:-}" ]; then
    printf '%s' "$KEY" > "$HOME/.serverchan_key"
    chmod 600 "$HOME/.serverchan_key"
    echo "Saved to ~/.serverchan_key"
  fi
fi

say "Log in to claude.ai — a browser window will open"
echo "Use YOUR own account. Tip: prefer claude.ai's EMAIL CODE login; Google SSO"
echo "is often blocked inside automation browsers."
"$PY" claude_warmup_usage.py bootstrap || die "login (bootstrap) did not complete — re-run ./install.sh"

say "Setup complete 🎉"
echo "Verify now:   $PY claude_warmup_usage.py run --test"
echo
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
  WINPS="$(wslpath -w "$HERE/examples/windows-schtasks/setup-tasks.ps1" 2>/dev/null || echo "$HERE/examples/windows-schtasks/setup-tasks.ps1")"
  echo "Scheduling (you're on WSL) — run this in a Windows PowerShell window:"
  echo "    powershell.exe -ExecutionPolicy Bypass -File \"$WINPS\""
  echo "  (edit the variables at the top of that file first if you cloned elsewhere)."
else
  echo "Scheduling (Linux) — see: examples/linux-systemd/README.md"
fi
