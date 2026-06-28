# claude-warmup-usage

Keep your **claude.ai interactive 5‑hour usage window** warm and get usage
reports pushed to your phone — driven by a **real browser** (Playwright), not the
API.

> Since 2026‑06‑15, hitting Claude through the API / Agent SDK / `ccusage` /
> `claude -p` runs on a *separate automation billing pool*: it does **not** light
> up your interactive 5‑hour window, and it can't read the official window‑reset
> numbers. This tool therefore drives the **claude.ai web app** in a headless
> Chromium so that a tiny daily message actually starts/keeps your interactive
> window, and reads usage straight from claude.ai's own endpoint.

## ⚠️ Disclaimer

This is a personal‑productivity tool for **your own paid Claude account**. It
sends *one tiny message* when needed and reads *your own* usage page. You are
responsible for complying with Anthropic's Terms of Service. Use at your own
risk. Don't use it to abuse, share, or resell access.

## What it does

- **Warm up**: when your 5‑hour window is dormant, send one minimal message
  (default `"ok"`) into **a single, reused conversation** to (re)start the window.
- **Report usage**: read `5h window` + `weekly` utilization & reset times from
  claude.ai's usage endpoint and push a short summary via [Server酱](https://sct.ftqq.com/)
  (ServerChan).
- **Self‑heal**: if the session has expired, it pushes a "please re‑login" alert
  and exits non‑zero.

## How it works

- Uses **Playwright**'s bundled Chromium with a **persistent profile**
  (`~/.claude_profile`) so it stays logged in.
- Headless runs use full Chrome via `--headless=new` and override the
  user‑agent to the *headed* `Chrome/<v>` string — otherwise Playwright's
  `HeadlessChrome` UA invalidates the Cloudflare `cf_clearance` cookie and you
  get a `403`.
- Reads usage from `GET https://claude.ai/api/organizations/<org>/usage`
  (org id auto‑captured at runtime), with a DOM scrape as fallback.

## Requirements

- Linux **with a graphical session**, or **Windows + WSL2** (tested on Ubuntu
  24.04 under WSLg). A display is needed *once*, for the login window.
- Python 3.10+.
- A [Server酱](https://sct.ftqq.com/) SendKey (optional; without it, it just logs/prints).

## 🚀 Quick start (one command)

```bash
git clone https://github.com/jackdhch/claude-warmup-usage.git && cd claude-warmup-usage && ./install.sh
```

`install.sh` creates the venv, installs Playwright + Chromium, optionally saves
your Server酱 key, then **opens a browser so you log into your own account**.
When it finishes it prints the one command to set up scheduling for your
platform. To verify right away:

```bash
.venv/bin/python claude_warmup_usage.py run --test
```

> **What can't be one-click:** the login itself. You must sign in with **your
> own** claude.ai account (email code + 2FA) in the browser window the installer
> opens — only you can do that. Everything else is automated. On a *headless*
> server with no display, do `bootstrap` once on a machine that has a display,
> then copy `~/.claude_profile` over.

<details>
<summary>Manual install (if you'd rather not use install.sh)</summary>

```bash
git clone https://github.com/jackdhch/claude-warmup-usage.git
cd claude-warmup-usage
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # add --with-deps if libs are missing (needs sudo)
python claude_warmup_usage.py bootstrap
```

On Ubuntu, if `python3 -m venv` complains about `ensurepip`, either
`sudo apt install python3-venv`, or create it `--without-pip` and bootstrap
with `get-pip.py`.
</details>

## Usage

```bash
python claude_warmup_usage.py bootstrap     # one-time: opens a window to log in (incl. 2FA)
python claude_warmup_usage.py discover      # (optional) dump usage endpoint + selectors
python claude_warmup_usage.py run           # activate-if-needed + read usage + push
python claude_warmup_usage.py run --auto    # only if window dormant AND it's 09:00–24:00
python claude_warmup_usage.py run --force   # always send + push (counts toward daily cap)
python claude_warmup_usage.py run --test    # like --force, but bypasses the daily push cap
python claude_warmup_usage.py publish       # read-only: fetch usage + write to a secret Gist (for widgets)
```

**Login note:** Google SSO is often blocked inside automation browsers
(`gis_transform 400`). Use claude.ai's **email code** login instead — it logs
into the same account. If a magic *link* is emailed, paste it into the *same*
Chromium window.

## Behavior rules (configurable in the source)

- **One conversation**: every warmup reuses `config.conversation_url` instead of
  spawning a new chat.
- **Conditional activation**: `run` / `run --auto` only send a message (and only
  push) when the 5‑hour window actually needs activation. "Needs activation" is
  judged by `five_hour.resets_at` being in the past (NOT the API's `is_active`
  flag, which flips to `False` even while a window is still open). If it's still
  active, they do nothing and stay silent. `--force` / `--test` override.
- **Minimum gap**: a hard floor (`MIN_ACTIVATION_GAP_HOURS`, default **5h**)
  between our own activations — recorded in state as `last_activation` — so even
  hourly polling can never message you more than once per 5 hours.
- **Work hours**: `run --auto` only acts during `09:00–24:00` local time.
- **Daily push cap**: at most **3** Server酱 pushes per local day
  (`MAX_PUSHES_PER_DAY`); `--test` bypasses it.

## Configuration & files

Server酱 key is read from (in order): env `SERVERCHAN_KEY` →
`~/.claude-warmup-config.json` (`serverchan_key`) → `~/.serverchan_key`.

| Path | Purpose |
|---|---|
| `~/.claude_profile/` | persistent browser profile (login) |
| `~/.claude-warmup-config.json` | `user_agent`, `org_id`, `conversation_url`, `gist_id`, `gist_raw_url` |
| `~/.claude-warmup-state.json` | per‑day push counter + `last_activation` |
| `~/.serverchan_key` | Server酱 SendKey (chmod 600) |
| `~/.claude-warmup.log` | run log |

## Scheduling

- **Windows + WSL** → see [`examples/windows-schtasks/`](examples/windows-schtasks/):
  a PowerShell script registers a weekday‑morning task (wakes the PC) and an
  hourly work‑hours `--auto` task.
- **Native Linux** → see [`examples/linux-systemd/`](examples/linux-systemd/):
  user systemd timers (enable `loginctl enable-linger` to run while logged out),
  plus a cron one‑liner.

## Apple Watch / iPhone widgets

`publish` reads usage **read‑only** (no message, no window consumed) and writes a
small JSON to a **secret GitHub Gist** via the `gh` CLI — so a watch/phone widget
can fetch it over the internet without any always‑on Mac or self‑hosting. Schedule
it every ~30 minutes on your always‑on machine; the raw URL is saved to
`gist_raw_url` in the config.

```jsonc
{
  "schema": 1,
  "five_hour": { "used_pct": 60, "remaining_pct": 40, "resets_at": "…", "resets_in_min": 171 },
  "seven_day": { "used_pct": 85, "remaining_pct": 15, "resets_at": "…", "resets_in_min": 1971 },
  "updated_at": "2026-06-28T23:08:47+08:00",
  "updated_epoch": 1782659327
}
```

A native watchOS complication/app (built in Xcode) and a Mac‑free iPhone widget
(via Scriptable) that read this endpoint are planned under `watch/`.

## License

[MIT](LICENSE)
