# claude-warmup-usage

用**真实浏览器**(Playwright)给你的 **claude.ai 5 小时交互用量窗口**保活,并把用量报告推送到手机——不走 API。

> 自 2026‑06‑15 起,通过 API / Agent SDK / `ccusage` / `claude -p` 调用 Claude 会走**独立的自动化计费池**:既**不会点亮**你的 5 小时交互窗口,也读不到官方的窗口重置数值。因此本工具用无头 Chromium 驱动 **claude.ai 网页**,用每天一条极小的消息真正开启/保持交互窗口,并直接从 claude.ai 自己的接口读取用量。

> 🌐 English version is appended at the bottom of this file.

## ⚠️ 免责声明

这是给**你自己的付费 Claude 账号**用的个人效率小工具。它只在需要时发**一条极小的消息**,并读取**你自己的**用量页面。你需自行遵守 Anthropic 的服务条款,风险自负。请勿用于滥用、共享或转售访问权限。

## 功能

- **预热**:当 5 小时窗口休眠时,向**同一个复用的对话**发一条最小消息(默认 `"ok"`)来(重新)开启窗口。
- **用量上报**:从 claude.ai 用量接口读取 `5 小时窗口` + `每周` 的使用率和重置时间,通过 [Server酱](https://sct.ftqq.com/) 推送简短摘要。
- **自愈**:会话过期时,推送一条"请重新登录"提醒并以非零码退出。

## 工作原理

- 使用 **Playwright** 自带的 Chromium + **持久化 profile**(`~/.claude_profile`),保持登录态。
- 无头运行用 `--headless=new`(完整 Chrome),并把 UA 改成**有头**时的 `Chrome/<版本>`——否则 Playwright 的 `HeadlessChrome` UA 会让 Cloudflare 的 `cf_clearance` cookie 失效、返回 `403`。
- 用量从 `GET https://claude.ai/api/organizations/<org>/usage` 读取(org id 运行时自动捕获),并以 DOM 抓取兜底。

## 环境要求

- **带图形界面的 Linux**,或 **Windows + WSL2**(在 Ubuntu 24.04 + WSLg 上测试)。登录窗口**需要一次**图形界面。
- Python 3.10+。
- 一个 [Server酱](https://sct.ftqq.com/) SendKey(可选;没有就只记录/打印)。

## 🚀 一键部署(一条命令)

```bash
git clone https://github.com/jackdhch/claude-warmup-usage.git && cd claude-warmup-usage && ./install.sh
```

`install.sh` 会建好 venv、安装 Playwright + Chromium、(可选)保存你的 Server酱 key,然后**弹出浏览器让你登录自己的账号**;完成后会按你的平台打印一条设置定时任务的命令。想立刻验证:

```bash
.venv/bin/python claude_warmup_usage.py run --test
```

> **唯一不能"一键"的是登录本身**:你必须在安装脚本弹出的浏览器里用**自己的** claude.ai 账号(邮箱验证码 + 2FA)登录——只有你能做,其余全自动。纯**无显示器**的服务器:先在有图形界面的机器上 `bootstrap` 一次,再把 `~/.claude_profile` 拷过去。

<details>
<summary>手动安装(不想用 install.sh 的话)</summary>

```bash
git clone https://github.com/jackdhch/claude-warmup-usage.git
cd claude-warmup-usage
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # 缺系统库时加 --with-deps(需要 sudo)
python claude_warmup_usage.py bootstrap
```

在 Ubuntu 上,如果 `python3 -m venv` 报缺 `ensurepip`:要么 `sudo apt install python3-venv`,要么用 `--without-pip` 创建再用 `get-pip.py` 引导 pip。
</details>

## 用法

```bash
python claude_warmup_usage.py bootstrap     # 仅一次:弹窗登录(含 2FA)
python claude_warmup_usage.py discover      # (可选)导出用量接口与选择器
python claude_warmup_usage.py run           # 需要时激活 + 读用量 + 推送
python claude_warmup_usage.py run --auto    # 仅当窗口休眠且在 09:00–24:00 时
python claude_warmup_usage.py run --force   # 无条件发送 + 推送(计入每日上限)
python claude_warmup_usage.py run --test    # 同 --force,但不受每日推送上限限制
```

**登录提示**:Google SSO 在自动化浏览器里常被拦(`gis_transform 400`)。请改用 claude.ai 的**邮箱验证码**登录——登的是同一个账号。如果邮件给的是登录**链接**,把它粘贴到**同一个** Chromium 窗口里打开。

## 行为规则(源码内可配置)

- **单一对话**:每次预热都复用 `config.conversation_url`,不会每次新开对话。
- **按需激活**:`run` / `run --auto` 仅在 5 小时窗口确实需要激活时才发消息(且仅此时才推送)。"是否需要激活"看 `five_hour.resets_at` 是否已过期(**不看** API 的 `is_active`——它在窗口仍开着时也会变 `False`)。窗口仍活跃则静默。`--force` / `--test` 可强制。
- **最小间隔**:两次激活之间有**硬性下限**(`MIN_ACTIVATION_GAP_HOURS`,默认 **5 小时**),记录在状态文件的 `last_activation` 里——即使每小时轮询,也绝不会更频繁地打扰你。
- **工作时间**:`run --auto` 仅在本地时间 `09:00–24:00` 动作。
- **每日推送上限**:每个本地日最多 **3** 条 Server酱 推送(`MAX_PUSHES_PER_DAY`);`--test` 不受此限。

## 配置与文件

Server酱 key 读取顺序:环境变量 `SERVERCHAN_KEY` → `~/.claude-warmup-config.json`(`serverchan_key`)→ `~/.serverchan_key`。

| 路径 | 用途 |
|---|---|
| `~/.claude_profile/` | 持久化浏览器 profile(登录态) |
| `~/.claude-warmup-config.json` | `user_agent`、`org_id`、`conversation_url` |
| `~/.claude-warmup-state.json` | 每日推送计数 + `last_activation` |
| `~/.serverchan_key` | Server酱 SendKey(权限 600) |
| `~/.claude-warmup.log` | 运行日志 |

## 定时调度

- **Windows + WSL** → 见 [`examples/windows-schtasks/`](examples/windows-schtasks/):一个 PowerShell 脚本会注册"工作日早晨任务(唤醒电脑)"和"工作时间每小时 `--auto` 任务"。
- **原生 Linux** → 见 [`examples/linux-systemd/`](examples/linux-systemd/):用户级 systemd 定时器(用 `loginctl enable-linger` 可在注销后仍运行),另附 cron 一行写法。

## 许可证

[MIT](LICENSE)

<br>

---

<br>

# English version

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

## License

[MIT](LICENSE)
