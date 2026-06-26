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

- Linux, or **Windows + WSL2** (tested on Ubuntu 24.04 under WSLg).
- Python 3.10+.
- A [Server酱](https://sct.ftqq.com/) SendKey (optional; without it, it just logs/prints).

## Install

```bash
git clone https://github.com/<you>/claude-warmup-usage.git
cd claude-warmup-usage
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # add --with-deps if libs are missing (needs sudo)
```

> On Ubuntu, if `python3 -m venv` complains about `ensurepip`, either
> `sudo apt install python3-venv`, or create it `--without-pip` and bootstrap
> with `get-pip.py`.

## Usage

```bash
python claude_warmup_usage.py bootstrap     # one-time: opens a window to log in (incl. 2FA)
python claude_warmup_usage.py discover      # (optional) dump usage endpoint + selectors
python claude_warmup_usage.py run           # activate-if-needed + read usage + push
python claude_warmup_usage.py run --auto    # only if window dormant AND it's 09:00–24:00
python claude_warmup_usage.py run --force   # always send + push (counts toward daily cap)
python claude_warmup_usage.py run --test    # like --force, but bypasses the daily push cap
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
| `~/.claude-warmup-config.json` | `user_agent`, `org_id`, `conversation_url` |
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

## 中文说明

用**真实浏览器**(Playwright 驱动 claude.ai 网页)给你的 **5 小时交互窗口**保活,并把用量通过 **Server酱**推到手机。
自 2026‑06‑15 起,API / Agent SDK / ccusage / `claude -p` 走独立自动化计费池,**不点亮交互窗口**、也读不到官方窗口重置值,所以必须走浏览器。

- `bootstrap` 有头登录(只跑一次,支持邮箱验证码 + 2FA;Google 登录常被自动化浏览器拦,改用邮箱验证码)。
- `run` 仅在窗口需要激活时才发一条最小消息(默认 `ok`),并**复用同一个对话**;读官方 `/usage` 接口拿到 5 小时 + 每周的剩余/重置,推送给你。
- `run --auto`:仅在 **09:00–24:00** 且窗口已过期(看 `resets_at`,**不看会抽风的 `is_active`**)时激活。
- **硬性下限**:两次激活至少间隔 **5 小时**(`MIN_ACTIVATION_GAP_HOURS`,记录在 `last_activation`),即使每小时轮询也绝不会更频繁地打扰你。
- 每天 Server酱 推送 **≤ 3 次**(`--test` 不受限、也不计数)。
- 调度:Windows+WSL 用 `examples/windows-schtasks/`;原生 Linux 用 `examples/linux-systemd/`。

## License

[MIT](LICENSE)
