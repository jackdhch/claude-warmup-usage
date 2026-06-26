#!/usr/bin/env python3
"""
claude_warmup_usage.py

A small Playwright tool that drives the real claude.ai web UI to:
  (1) "warm up" the interactive 5-hour usage window by sending one tiny message, and
  (2) read current usage (5h window remaining + reset time + weekly) and push it via Server酱.

HARD CONSTRAINT: everything goes through a real browser (Playwright + claude.ai).
We deliberately do NOT use `claude -p`, the Agent SDK, ccusage, or the Anthropic API:
since 2026-06-15 those run on a separate automation billing pool, do not light up the
interactive window, and cannot read the official window-reset numbers.

Subcommands:
  bootstrap   Headed login (run once). Opens claude.ai so you can log in (incl. 2FA),
              then saves the persistent profile to ~/.claude_profile.
  discover    Headless. Opens /new and /settings/usage, logs every usage/rate-limit-looking
              response (URL + JSON preview), plus candidate input selectors and usage-page
              DOM nodes. Use its output to confirm the real endpoint + selectors.
  run         Headless (for cron). Loads the profile; if bounced to /login, pushes a
              "login expired" alert and exits non-zero. Otherwise sends one message,
              reads usage, and pushes a short summary via Server酱.

Logs to ~/.claude-warmup.log
"""

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths / constants
# ----------------------------------------------------------------------------
HOME = Path.home()
PROFILE_DIR = HOME / ".claude_profile"
LOG_FILE = HOME / ".claude-warmup.log"
DISCOVER_OUT = HOME / ".claude-discover.txt"

URL_NEW = "https://claude.ai/new"
URL_USAGE = "https://claude.ai/settings/usage"
URL_HOME = "https://claude.ai/"

DEFAULT_MESSAGE = "ok"

# Small JSON config persisted next to the log. `bootstrap` writes the real
# headed user-agent here so `run` can present an identical fingerprint.
# It also holds org_id and the reused conversation_url.
CONFIG_FILE = HOME / ".claude-warmup-config.json"
# Mutable per-day state: Server酱 push counter (resets daily).
STATE_FILE = HOME / ".claude-warmup-state.json"

# Server酱 daily push cap, and the work-hours window for --auto activation.
MAX_PUSHES_PER_DAY = 3
WORK_START_HOUR = 9     # inclusive
WORK_END_HOUR = 24      # exclusive -> active for local hours 9..23 (09:00–24:00)
# Hard floor between our own activations: never send more often than this,
# regardless of what the usage API reports. The 5-hour window is this long.
MIN_ACTIVATION_GAP_HOURS = 5

# ============================================================================
# === CONFIRMED BY `discover` (real values read from live claude.ai) =========
# ============================================================================
# Usage JSON endpoint:  GET https://claude.ai/api/organizations/<ORG>/usage
#   shape: {"five_hour":{"utilization":<%used>,"resets_at":<iso>},
#           "seven_day":{"utilization":<%used>,"resets_at":<iso>},
#           "seven_day_opus":null|{...}, "seven_day_sonnet":null|{...}, ...}
# Org id is auto-captured at runtime from claude.ai's /api/organizations/<org>/
# requests (and from config.org_id). Leave None; no need to hardcode it.
FALLBACK_ORG_ID = None
USAGE_PATH_SUFFIX = "/usage"          # path (sans query) ends with this, under /api/organizations/

# Composer input box on /new (data-testid is the stable hook):
INPUT_SELECTOR = '[data-testid="chat-input"]'

# Cloudflare binds cf_clearance to the UA. Playwright's headless build reports a
# "HeadlessChrome" token which both invalidates the clearance cookie AND flags
# the bot -> 403. So in headless `run` we override the UA to the exact *headed*
# string (captured at bootstrap; this constant is the known-good fallback).
FALLBACK_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")
# ============================================================================

# Generic hints used by discover (and as a backup matcher) to spot usage traffic.
URL_USAGE_HINTS = ["usage", "rate_limit", "rate-limit", "ratelimit", "limit",
                   "quota", "remaining", "reset", "subscription", "billing"]
INPUT_SELECTOR_CANDIDATES = [
    '[data-testid="chat-input"]',
    'div.ProseMirror[contenteditable="true"]',
    'div[contenteditable="true"][role="textbox"]',
    'div[contenteditable="true"]',
    '[role="textbox"]',
    'textarea',
]
ORG_RE = re.compile(r"/api/organizations/([0-9a-f-]{36})/")

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
def get_logger() -> logging.Logger:
    log = logging.getLogger("warmup")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except Exception as e:  # logging must never crash the tool
        print(f"WARN: cannot open log file {LOG_FILE}: {e}", file=sys.stderr)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log


LOG = get_logger()


def retry(fn, attempts=3, delay=3.0, what="operation"):
    """Run fn() with retries; raise the last exception if all fail."""
    last = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            LOG.warning("%s 失败(第 %d/%d 次):%s", what, i, attempts, e)
            if i < attempts:
                time.sleep(delay)
    raise last


# ----------------------------------------------------------------------------
# Tiny JSON config (persists the headed user-agent + org id from bootstrap).
# ----------------------------------------------------------------------------
def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(updates: dict) -> None:
    cfg = load_config()
    cfg.update({k: v for k, v in updates.items() if v})
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        LOG.info("已保存配置 -> %s", CONFIG_FILE)
    except Exception as e:  # noqa: BLE001
        LOG.warning("写入配置失败:%s", e)


def resolved_ua() -> str:
    """The UA to present in headless run: the headed UA captured at bootstrap,
    else the known-good fallback. Never contains a 'Headless' token."""
    ua = (load_config().get("user_agent") or "").strip()
    if ua and "Headless" not in ua:
        return ua
    return FALLBACK_UA


# ----------------------------------------------------------------------------
# Per-day mutable state (Server酱 push counter, capped at MAX_PUSHES_PER_DAY).
# ----------------------------------------------------------------------------
def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(st: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        LOG.warning("写入状态文件失败:%s", e)


def _today() -> str:
    return dt.date.today().isoformat()


def pushes_today() -> int:
    st = load_state()
    return st.get("push_count", 0) if st.get("push_date") == _today() else 0


def last_activation_ts() -> str:
    """ISO timestamp of the last message WE sent to (re)start the window, or ''."""
    return load_state().get("last_activation", "")


def record_activation() -> None:
    st = load_state()
    st["last_activation"] = dt.datetime.now().astimezone().isoformat()
    save_state(st)
    LOG.info("已记录本次激活时间:%s", st["last_activation"])


def hours_since_last_activation() -> float:
    """Hours since our last activation; large number if never / unparseable."""
    iso = last_activation_ts()
    if not iso:
        return 1e9
    try:
        d = dt.datetime.fromisoformat(iso)
        now = dt.datetime.now(d.tzinfo) if d.tzinfo else dt.datetime.now()
        return (now - d).total_seconds() / 3600.0
    except Exception:
        return 1e9


def in_work_hours() -> bool:
    h = dt.datetime.now().hour
    return WORK_START_HOUR <= h < WORK_END_HOUR


# ----------------------------------------------------------------------------
# Server酱 push (SendKey from env SERVERCHAN_KEY). Supports Turbo (SCT...) and
# Server酱³ (sctp...) endpoints.
# ----------------------------------------------------------------------------
def push_serverchan(title: str, desp: str, bypass_cap: bool = False) -> bool:
    """推送 Server酱 通知,默认受每日 MAX_PUSHES_PER_DAY 次上限约束(按本地日计数,
    所有推送——常规与告警——都计入,符合用户"每天不超过3次"的规则)。
    bypass_cap=True 用于单次手动测试:不受上限限制、也不计入计数。"""
    # 先做每日上限判断(跨天自动清零;就地更新,保留 last_activation 等其它键)。
    st = load_state()
    if st.get("push_date") != _today():
        st["push_date"] = _today()
        st["push_count"] = 0
    if not bypass_cap and st.get("push_count", 0) >= MAX_PUSHES_PER_DAY:
        LOG.warning("已达每日 Server酱 上限(%d 次),本次不推送:%s",
                    MAX_PUSHES_PER_DAY, title)
        return False

    # Primary: env var SERVERCHAN_KEY (per spec). Fallbacks for the scheduled
    # task so the secret need not sit in the schtasks command line.
    key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if not key:
        key = (load_config().get("serverchan_key") or "").strip()
    if not key:
        try:
            key = (HOME / ".serverchan_key").read_text(encoding="utf-8").strip()
        except Exception:
            key = ""
    if not key:
        LOG.error("未设置 SERVERCHAN_KEY(环境变量 / 配置 / ~/.serverchan_key 均无),无法推送。标题:%s", title)
        return False
    try:
        import requests
    except Exception as e:  # noqa: BLE001
        LOG.error("未安装 requests(%s),无法推送", e)
        return False

    if key.startswith("sctp"):
        m = re.match(r"sctp(\d+)t", key)
        uid = m.group(1) if m else ""
        url = f"https://{uid}.push.ft07.com/send/{key}.send"
    else:
        url = f"https://sctapi.ftqq.com/{key}.send"

    # Server酱 把 desp 当 Markdown 渲染,单个 \n 不会换行。把每个换行改成
    # Markdown 硬换行(行尾两个空格 + \n),这样手机上每行才会单独成行。
    desp_md = desp.replace("\n", "  \n")

    try:
        r = retry(lambda: requests.post(url, data={"title": title, "desp": desp_md}, timeout=20),
                  attempts=3, delay=4.0, what="Server酱推送")
        ok = r.status_code == 200
        body = (r.text or "")[:300]
        success = ok and ('"code":0' in body or '"errno":0' in body
                          or '"success"' in body.lower() or "data" in body)
        if (success or ok) and not bypass_cap:
            # 仅在真正发出(返回 200)且非测试时计入当日次数。
            st["push_count"] = st.get("push_count", 0) + 1
            save_state(st)
        if success:
            LOG.info("Server酱 推送成功(今日 %d/%d%s):%s",
                     st.get("push_count", 0), MAX_PUSHES_PER_DAY,
                     ",测试不计数" if bypass_cap else "", title)
            return True
        LOG.warning("Server酱 返回 status=%s body=%s", r.status_code, body)
        return ok
    except Exception as e:  # noqa: BLE001
        LOG.error("Server酱 推送失败:%s", e)
        return False


# ----------------------------------------------------------------------------
# Playwright helpers
# ----------------------------------------------------------------------------
def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa
        return sync_playwright
    except Exception as e:  # noqa: BLE001
        LOG.error("无法导入 Playwright:%s", e)
        LOG.error("请激活 venv 并执行 `pip install playwright && playwright install chromium`。")
        raise


def launch_context(p, headed: bool):
    """Open the persistent context rooted at PROFILE_DIR.

    Two modes (both verified against Cloudflare on this machine):
      headed=True  -> a real visible window via WSLg, NATIVE user-agent.
                      Used by `bootstrap` so cf_clearance is issued natively.
      headed=False -> full Chrome in NEW headless mode (`--headless=new`):
                      no window, NO $DISPLAY required, and we override the UA
                      to the captured headed string so the 'Headless' token is
                      gone and cf_clearance stays valid (plain headless=True
                      uses the headless-shell build whose UA -> 403).
    """
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]
    if not headed:
        args.append("--headless=new")  # full chrome, headless, no display needed
    kwargs = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=False,                # we control headlessness via --headless=new
        viewport={"width": 1280, "height": 900},
        locale="en-US",
        args=args,
        ignore_default_args=["--enable-automation"],
    )
    if not headed:
        kwargs["user_agent"] = resolved_ua()
        LOG.info("启动:无头模式(new-headless),UA=%s", kwargs["user_agent"])
    else:
        LOG.info("启动:有头窗口(原生 UA)")
    ctx = p.chromium.launch_persistent_context(**kwargs)
    ctx.set_default_timeout(45_000)
    ctx.set_default_navigation_timeout(60_000)
    # Mask the most common automation fingerprints.
    try:
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "window.chrome=window.chrome||{runtime:{}};"
            "Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});"
        )
    except Exception:
        pass
    return ctx


def looks_logged_out(page) -> bool:
    u = (page.url or "").lower()
    return "/login" in u or "/auth/" in u or "magic-link" in u


# ----------------------------------------------------------------------------
# Subcommand: bootstrap
# ----------------------------------------------------------------------------
def cmd_bootstrap(args) -> int:
    sync_playwright = _import_playwright()
    LOG.info("bootstrap:启动有头 Chromium 供手动登录……")
    print("\n" + "=" * 70)
    print("将通过 WSLg 弹出一个 Chromium 窗口。步骤:")
    print("  1. 正常登录 claude.ai —— 邮箱/Google,需要时输入 2FA。")
    print("  2. 等到能看见聊天输入框(主界面)。")
    print("  3. 回到这里按【回车】保存登录态。")
    print("若没有窗口弹出,说明 WSLg/$DISPLAY 不可用 —— 见末尾的排查提示。")
    print("=" * 70 + "\n")

    try:
        with sync_playwright() as p:
            try:
                ctx = launch_context(p, headed=True)
            except Exception as e:  # noqa: BLE001
                LOG.error("有头启动失败:%s", e)
                print("\n有头启动失败,通常是没有显示器。解决办法:")
                print("  • 确认 WSLg 正常:`echo $DISPLAY` 应输出 ':0'。")
                print("  • 在 Windows 上更新 WSL:wsl --update(然后重启 WSL)。")
                print("  • 或从 Windows 终端运行 bootstrap,以便挂上 WSLg。")
                return 3
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(URL_HOME, wait_until="domcontentloaded")
            try:
                input("登录完成并看到聊天界面后,在此按【回车】…… ")
            except EOFError:
                LOG.warning("无标准输入;改为等待 120 秒供手动登录。")
                time.sleep(120)

            # 校验确实已登录。
            page.goto(URL_NEW, wait_until="domcontentloaded")
            time.sleep(3)
            if looks_logged_out(page):
                LOG.error("仍停留在登录页(%s),登录未完成。", page.url)
                print("\n未检测到登录。请重新运行 bootstrap 并先完成登录。")
                ctx.close()
                return 4
            LOG.info("已登录,当前 URL:%s", page.url)
            # 抓取有头 UA + org id,使无头 run 的指纹与 cf_clearance 匹配。
            try:
                ua = page.evaluate("navigator.userAgent")
                org = None
                m = ORG_RE.search(page.content() or "")
                save_config({"user_agent": ua, "org_id": org})
                LOG.info("已记录有头 UA:%s", ua)
            except Exception as e:  # noqa: BLE001
                LOG.warning("未能记录 UA:%s", e)
            print(f"\n已检测到登录(URL:{page.url})。正在保存 profile 到 {PROFILE_DIR} ……")
            ctx.close()  # 持久上下文在关闭时自动落盘
    except Exception as e:  # noqa: BLE001
        LOG.exception("bootstrap 异常:%s", e)
        return 1

    print("Bootstrap 完成。下一步:运行 `discover` 确认接口与选择器。")
    LOG.info("bootstrap 完成。")
    return 0


# ----------------------------------------------------------------------------
# Subcommand: discover
# ----------------------------------------------------------------------------
def cmd_discover(args) -> int:
    sync_playwright = _import_playwright()
    out_lines = []

    def emit(s=""):
        print(s)
        out_lines.append(str(s))

    captured = []  # list of dicts: url, status, ctype, body(optional)

    def on_response(resp):
        try:
            url = resp.url
            ctype = (resp.headers or {}).get("content-type", "")
            status = resp.status
            low = url.lower()
            url_hit = any(h in low for h in URL_USAGE_HINTS)
            is_json = "json" in ctype.lower()
            rec = {"url": url, "status": status, "ctype": ctype, "body": None, "match": ""}
            if url_hit:
                rec["match"] = "url"
            # Pull body for json responses (so we can also detect by body keys).
            if is_json and ("/api/" in low or url_hit):
                try:
                    txt = resp.text()
                    if any(k in txt.lower() for k in
                           ["reset", "remaining", "limit", "utilization", "five_hour",
                            "weekly", "window", "usage", "quota"]):
                        rec["match"] = (rec["match"] + "+body").strip("+")
                    rec["body"] = txt[:6000]
                except Exception:
                    pass
            captured.append(rec)
        except Exception:
            pass

    try:
        with sync_playwright() as p:
            ctx = launch_context(p, headed=getattr(args, "headed", False))
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.on("response", on_response)

            emit("=" * 78)
            emit("DISCOVER — navigating /new")
            emit("=" * 78)
            page.goto(URL_NEW, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass
            time.sleep(3)

            if looks_logged_out(page):
                emit(f"!! Looks logged out (URL={page.url}). Run bootstrap first.")
                ctx.close()
                return 4

            # Candidate input selectors on /new
            emit("\n--- INPUT CANDIDATES on /new ---")
            cands = page.evaluate(
                """() => {
                    const out = [];
                    const els = document.querySelectorAll(
                        '[contenteditable="true"], textarea, [role="textbox"]');
                    els.forEach(el => {
                        const cls = (el.className && el.className.toString) ? el.className.toString() : '';
                        out.push({
                            tag: el.tagName.toLowerCase(),
                            id: el.id || '',
                            classes: cls,
                            role: el.getAttribute('role') || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            placeholder: el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || '',
                            testid: el.getAttribute('data-testid') || '',
                            contenteditable: el.getAttribute('contenteditable') || '',
                            visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
                        });
                    });
                    return out;
                }"""
            )
            for c in cands:
                emit(json.dumps(c, ensure_ascii=False))
            if not cands:
                emit("(no contenteditable/textarea/textbox elements found)")

            emit("\n" + "=" * 78)
            emit("DISCOVER — navigating /settings/usage")
            emit("=" * 78)
            page.goto(URL_USAGE, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=25_000)
            except Exception:
                pass
            time.sleep(4)

            # Usage-page DOM nodes mentioning reset/limit/remaining/week/%
            emit("\n--- USAGE-PAGE DOM NODES (reset|limit|remaining|week|%) ---")
            nodes = page.evaluate(
                r"""() => {
                    const rx = /(reset|limit|remaining|week|weekly|%|hour)/i;
                    const out = [];
                    const all = document.querySelectorAll('body *');
                    for (const el of all) {
                        if (el.children.length > 2) continue;       // prefer leaf-ish nodes
                        const t = (el.innerText || '').trim();
                        if (!t || t.length > 160) continue;
                        if (!rx.test(t)) continue;
                        const cls = (el.className && el.className.toString) ? el.className.toString() : '';
                        out.push({tag: el.tagName.toLowerCase(), classes: cls.slice(0,80), text: t});
                        if (out.length >= 80) break;
                    }
                    // de-dup by text
                    const seen = new Set(); const dedup = [];
                    for (const n of out) { if (!seen.has(n.text)) { seen.add(n.text); dedup.push(n); } }
                    return dedup;
                }"""
            )
            for n in nodes:
                emit(json.dumps(n, ensure_ascii=False))
            if not nodes:
                emit("(no matching DOM text nodes found)")

            time.sleep(2)
            ctx.close()
    except Exception as e:  # noqa: BLE001
        LOG.exception("discover 异常:%s", e)
        return 1

    # Print captured usage/rate-limit responses
    emit("\n" + "=" * 78)
    emit("CAPTURED RESPONSES (usage / rate-limit / json API)")
    emit("=" * 78)
    # First: the strong matches (url or body hit)
    strong = [r for r in captured if r["match"]]
    others = [r for r in captured if not r["match"] and "/api/" in r["url"].lower()]
    emit(f"\n>>> STRONG MATCHES ({len(strong)}):")
    for r in strong:
        emit(f"\n[{r['status']}] match={r['match']} ctype={r['ctype']}")
        emit(f"URL: {r['url']}")
        if r["body"]:
            emit("BODY (truncated):")
            emit(r["body"])
    emit(f"\n>>> OTHER /api/ JSON RESPONSES ({len(others)}) (URLs only):")
    for r in others:
        emit(f"[{r['status']}] {r['url']}")

    try:
        DISCOVER_OUT.write_text("\n".join(out_lines), encoding="utf-8")
        emit(f"\n(Full discover output also written to {DISCOVER_OUT})")
    except Exception as e:  # noqa: BLE001
        LOG.warning("写入 discover 输出文件失败:%s", e)
    return 0


# ----------------------------------------------------------------------------
# Usage JSON parsing — tuned to the real shape after discover.
# ----------------------------------------------------------------------------
def parse_usage_json(data: dict) -> dict:
    """Extract from the real /api/organizations/<org>/usage shape:
       five_hour.{utilization,resets_at}, seven_day.{utilization,resets_at},
       optional seven_day_opus / seven_day_sonnet / seven_day_cowork."""
    out = {"five_pct": None, "five_reset": None,
           "week_pct": None, "week_reset": None, "extra": []}
    if not isinstance(data, dict):
        return out

    def blk(name):
        b = data.get(name)
        return (b.get("utilization"), b.get("resets_at")) if isinstance(b, dict) else (None, None)

    out["five_pct"], out["five_reset"] = blk("five_hour")
    out["week_pct"], out["week_reset"] = blk("seven_day")
    for key, label in (("seven_day_opus", "Opus"),
                       ("seven_day_sonnet", "Sonnet"),
                       ("seven_day_cowork", "Cowork")):
        b = data.get(key)
        if isinstance(b, dict) and b.get("utilization") is not None:
            out["extra"].append((label, b.get("utilization"), b.get("resets_at")))
    return out


def _reset_in_past(value) -> bool:
    """True if the ISO timestamp is now/past (window expired)."""
    try:
        d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        now = dt.datetime.now(d.tzinfo) if d.tzinfo else dt.datetime.now()
        return (d - now).total_seconds() <= 0
    except Exception:
        return False


def needs_activation(data: dict) -> bool:
    """是否需要发一条消息来(重新)点亮 5 小时窗口?

    两道关卡(必须同时满足才返回 True):
      1) **硬性下限**:距我们上次激活不足 MIN_ACTIVATION_GAP_HOURS 小时 -> 一律 False。
         这是防"每小时误发"的根本保障,与接口无关。
      2) 5 小时窗口确实已过期:看 `five_hour.resets_at` 是否已过(或缺失)。
         注意:**故意不使用 `is_active`** —— 实测它在窗口仍开着(resets_at 在未来)
         时也会变 False,会导致每小时误激活。
    """
    if hours_since_last_activation() < MIN_ACTIVATION_GAP_HOURS:
        return False
    if not isinstance(data, dict):
        return True   # 已过 5h 下限且读不到用量:保守地激活一次
    ra = (data.get("five_hour") or {}).get("resets_at")
    if not ra:
        return True
    return _reset_in_past(ra)


def pct_remaining(used) -> str:
    try:
        return f"{100 - float(used):.0f}%"
    except Exception:
        return "?"


def reset_in(value) -> str:
    """Human 'time until reset' from an ISO timestamp."""
    try:
        d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        now = dt.datetime.now(d.tzinfo) if d.tzinfo else dt.datetime.now()
        secs = int((d - now).total_seconds())
        if secs <= 0:
            return "已到期"
        h, m = secs // 3600, (secs % 3600) // 60
        return f"{h}小时{m}分" if h else f"{m}分"
    except Exception:
        return "?"


def summarize_usage(data: dict, sent: bool) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    u = parse_usage_json(data)
    lines = []
    if u["five_pct"] is not None or u["five_reset"]:
        lines.append(f"🕔 5小时窗口:剩 {pct_remaining(u['five_pct'])}(已用 {u['five_pct']}%)")
        lines.append(f"重置 {fmt_reset(u['five_reset'])} · 还剩 {reset_in(u['five_reset'])}")
    if u["week_pct"] is not None or u["week_reset"]:
        lines.append(f"📅 每周(全模型):剩 {pct_remaining(u['week_pct'])}(已用 {u['week_pct']}%)")
        lines.append(f"重置 {fmt_reset(u['week_reset'])}")
    for label, pct, rs in u["extra"]:
        lines.append(f"📅 每周{label}:剩 {pct_remaining(pct)}(已用 {pct}%) · 重置 {fmt_reset(rs)}")
    lines.append("✅ 预热消息已发送" if sent else "⚠️ 未能确认消息已发送")
    lines.append(f"采集时间:{now}")
    lines.append("请到 claude.ai/settings/usage 核对 5 小时窗口已开始计时。")
    return "\n".join(lines)


def scrape_usage_dom(page) -> str:
    """Last-resort: scrape visible usage text from /settings/usage."""
    try:
        texts = page.evaluate(
            r"""() => {
                const rx = /(reset|limit|remaining|week|weekly|%|hour|session)/i;
                const out = [];
                for (const el of document.querySelectorAll('body *')) {
                    if (el.children.length > 2) continue;
                    const t = (el.innerText || '').trim();
                    if (t && t.length <= 120 && rx.test(t)) out.push(t);
                    if (out.length >= 60) break;
                }
                return [...new Set(out)];
            }"""
        )
    except Exception:
        texts = []
    return "\n".join(texts[:15])


def fmt_reset(value) -> str:
    """Turn an ISO timestamp / epoch into a friendly local string."""
    if value is None:
        return "?"
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            ts = float(value)
            if ts > 1e12:  # ms
                ts /= 1000.0
            d = dt.datetime.fromtimestamp(ts)
        else:
            s = str(value).replace("Z", "+00:00")
            d = dt.datetime.fromisoformat(s).astimezone()
        return d.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


# ----------------------------------------------------------------------------
# Subcommand: run
# ----------------------------------------------------------------------------
def fetch_usage(page, captured_org, usage_box):
    """读取用量 JSON:优先直连接口 GET,失败再用监听抓到的兜底。"""
    org = captured_org[0] or load_config().get("org_id") or FALLBACK_ORG_ID
    if not org:
        LOG.warning("未能确定组织 ID,改用监听抓取的用量兜底")
        return usage_box[-1] if usage_box else None
    usage_api = f"https://claude.ai/api/organizations/{org}/usage"
    LOG.info("请求用量接口 %s", usage_api)
    try:
        resp = retry(lambda: page.goto(usage_api, wait_until="domcontentloaded"),
                     attempts=3, delay=5, what="请求用量接口")
        if resp and resp.status == 200:
            d = json.loads(resp.text())
            LOG.info("用量接口 200:five_hour=%s", d.get("five_hour"))
            return d
        LOG.warning("用量接口返回 status=%s", resp.status if resp else None)
    except Exception as e:  # noqa: BLE001
        LOG.warning("用量接口请求失败:%s", e)
    if usage_box:
        LOG.info("改用监听抓到的用量作为兜底")
        return usage_box[-1]
    return None


def cmd_run(args) -> int:
    """读取用量,仅当"5 小时窗口需要激活"时才发一条消息激活,并仅在此时推送。
       - run        : 需要时即激活(不限时段),适合早晨预热。
       - run --auto : 需要时才激活,且仅在工作时间(09:00–24:00)。
       - run --force: 无条件发送并推送(手动 / 测试用)。
       窗口仍活跃时:不发消息、不推送。登录失效 / 异常会单独推送告警。"""
    sync_playwright = _import_playwright()
    message = args.message or DEFAULT_MESSAGE
    auto = getattr(args, "auto", False)
    force = getattr(args, "force", False)
    test = getattr(args, "test", False)
    if test:                       # 单次测试 = 强制发送 + 推送绕过每日上限
        force = True
    captured_org = [load_config().get("org_id")]
    usage_box = []  # 监听抓到的用量 JSON(备用)

    def on_response(resp):
        try:
            u = resp.url
            m = ORG_RE.search(u)
            if m and not captured_org[0]:
                captured_org[0] = m.group(1)
            ctype = (resp.headers or {}).get("content-type", "")
            if ("json" in ctype.lower() and "/api/organizations/" in u.lower()
                    and u.split("?")[0].endswith(USAGE_PATH_SUFFIX)):
                try:
                    usage_box.append(json.loads(resp.text()))
                except Exception:
                    pass
        except Exception:
            pass

    sent = False
    data = None
    dom_text = None
    mode = "auto" if auto else ("force" if force else "默认预热")
    try:
        with sync_playwright() as p:
            ctx = launch_context(p, headed=getattr(args, "headed", False))
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.on("response", on_response)

            # 1) 打开应用;若被重定向到登录页 -> 推送自愈提醒并以非零码退出。
            LOG.info("运行(%s):打开 %s", mode, URL_NEW)
            retry(lambda: page.goto(URL_NEW, wait_until="domcontentloaded"),
                  attempts=3, delay=5, what="打开 /new")
            time.sleep(3)
            if looks_logged_out(page):
                LOG.error("被重定向到登录页(%s),会话已失效。", page.url)
                push_serverchan("⚠️ Claude 预热失败:登录失效",
                                "claude.ai 会话已失效,请重新运行 bootstrap 登录。\n"
                                f"URL: {page.url}\n时间: {dt.datetime.now():%Y-%m-%d %H:%M}")
                ctx.close()
                return 2

            # 2) 先读用量,据此决定是否需要激活。
            data = fetch_usage(page, captured_org, usage_box)

            # 3) 决策:只有"需要激活(或 --force),且满足时段"才发送。
            need = needs_activation(data)
            work_ok = in_work_hours() if auto else True
            do_send = force or (need and work_ok)
            LOG.info("决策:需要激活=%s 工作时间=%s 强制=%s -> 发送=%s",
                     need, (work_ok if auto else "不限"), force, do_send)
            if do_send:
                sent = send_message(page, message)
                if sent:
                    record_activation()      # 记录时间戳,用于"至少间隔5小时"判断
                data = fetch_usage(page, captured_org, usage_box) or data
            else:
                gap = hours_since_last_activation()
                if not need and gap < MIN_ACTIVATION_GAP_HOURS:
                    reason = f"距上次激活仅 {gap:.1f}h(<{MIN_ACTIVATION_GAP_HOURS}h),无需激活"
                elif not need:
                    reason = "5 小时窗口仍活跃,无需激活"
                else:
                    reason = "不在工作时间(9:00–24:00)"
                LOG.info("本次不发送、不推送(%s)。", reason)
                ctx.close()
                print("本次无动作:" + reason)
                return 0

            # 4) 若接口未取到用量,退化到 DOM 抓取。
            if data is None:
                LOG.warning("接口未取到用量,退化到 /settings/usage 的 DOM 抓取。")
                try:
                    page.goto(URL_USAGE, wait_until="domcontentloaded")
                    try:
                        page.wait_for_load_state("networkidle", timeout=20_000)
                    except Exception:
                        pass
                    time.sleep(3)
                    if usage_box:
                        data = usage_box[-1]
                    else:
                        dom_text = scrape_usage_dom(page)
                except Exception as e:  # noqa: BLE001
                    LOG.warning("DOM 抓取失败:%s", e)

            ctx.close()
    except Exception as e:  # noqa: BLE001
        LOG.exception("运行异常:%s", e)
        push_serverchan("⚠️ Claude 预热脚本异常",
                        f"运行异常: {e}\n时间: {dt.datetime.now():%Y-%m-%d %H:%M}")
        return 1

    # 走到这里说明确实激活了窗口(否则上面已提前返回),此时才推送。
    if test:
        prefix = "🧪测试·模拟明早06:55预热 "
    elif auto:
        prefix = "🔁自动激活 "
    elif force:
        prefix = "🛠手动 "
    else:
        prefix = "🌅预热 "
    if data is not None:
        summary = summarize_usage(data, sent)
        title = f"{prefix}Claude 用量" if sent else f"{prefix}Claude(消息未确认)"
        rc = 0
    elif dom_text:
        summary = ("用量(DOM 兜底解析):\n" + dom_text +
                   f"\n{'✅ 已发送' if sent else '⚠️ 未确认发送'}  "
                   f"{dt.datetime.now():%Y-%m-%d %H:%M}")
        title = f"{prefix}Claude 用量(DOM 兜底)"
        rc = 0
    else:
        summary = (f"⚠️ 未能获取用量数值(接口与 DOM 均失败)。消息发送={sent}。\n"
                   f"时间: {dt.datetime.now():%Y-%m-%d %H:%M}")
        title = "⚠️ Claude:用量获取失败"
        rc = 5

    LOG.info("用量摘要:\n%s", summary)
    push_serverchan(title, summary, bypass_cap=test)
    print("\n=== 摘要 ===\n" + summary)
    print("\n提醒:请到 https://claude.ai/settings/usage 核对 5 小时窗口确已开始计时。")
    return rc


def send_message(page, message: str) -> bool:
    """Type one message and confirm it was sent. All warmups reuse ONE chat:
    config['conversation_url']. Try the saved chat first; on hard failure
    (bad/deleted url, no composer) fall back to /new and save the new id."""
    selectors = ([INPUT_SELECTOR] if INPUT_SELECTOR else []) + INPUT_SELECTOR_CANDIDATES

    def _send_on(url):
        retry(lambda: page.goto(url, wait_until="domcontentloaded"),
              attempts=2, delay=4, what=f"打开 {url}")
        time.sleep(2)
        if looks_logged_out(page):
            raise RuntimeError("打开对话时发现未登录")
        box = None
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                loc.wait_for(state="visible", timeout=8000)
                box = loc
                LOG.info("找到输入框(选择器:%s)", sel)
                break
            except Exception:
                continue
        if box is None:
            raise RuntimeError("未找到输入框")
        box.click()
        page.keyboard.type(message, delay=30)
        time.sleep(0.4)
        page.keyboard.press("Enter")
        # Universal confirmation: the composer clears after a successful send
        # (works for both a fresh /new and an existing /chat/<uuid>).
        ok = False
        try:
            page.wait_for_function(
                "() => { const e=document.querySelector('[contenteditable=\"true\"]');"
                " return !e || e.innerText.replace(/\\u00a0/g,'').trim()===''; }",
                timeout=15_000)
            ok = True
        except Exception:
            ok = "/chat/" in (page.url or "")
        if ok and "/chat/" in (page.url or ""):
            clean = (page.url or "").split("#")[0].split("?")[0]
            save_config({"conversation_url": clean})
            LOG.info("消息已发送;对话:%s", clean)
        elif ok:
            LOG.info("消息已发送(输入框已清空);url=%s", page.url)
        else:
            LOG.warning("未观察到发送确认信号;url=%s", page.url)
        return ok

    conv = (load_config().get("conversation_url") or "").strip()
    if conv:
        try:
            return retry(lambda: _send_on(conv), attempts=2, delay=4, what="发送(已保存对话)")
        except Exception as e:  # noqa: BLE001
            LOG.warning("在已保存对话发送失败(%s),改用 /new 重试", e)
    try:
        return retry(lambda: _send_on(URL_NEW), attempts=2, delay=4, what="发送(/new)")
    except Exception as e:  # noqa: BLE001
        LOG.error("发送消息失败:%s", e)
        return False


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="claude.ai warmup + usage via Playwright")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap", help="有头手动登录(只跑一次)")
    pd = sub.add_parser("discover", help="探测用量接口与候选选择器")
    pd.add_argument("--headed", action="store_true", help="用可见窗口运行(WSLg)")
    pr = sub.add_parser("run", help="读用量;需要时发1条消息激活窗口并推送(供计划任务)")
    pr.add_argument("--message", "-m", default=DEFAULT_MESSAGE, help="要发送的消息内容")
    pr.add_argument("--headed", action="store_true", help="用可见窗口运行(WSLg)")
    pr.add_argument("--auto", action="store_true",
                    help="仅当 5 小时窗口需要激活、且在工作时间(09:00–24:00)时才发送")
    pr.add_argument("--force", action="store_true",
                    help="无条件发送并推送(忽略是否需要/时段;手动或测试用)")
    pr.add_argument("--test", action="store_true",
                    help="单次测试:模拟早晨预热(强制发送),推送不受每日3次上限限制、也不计数")

    args = parser.parse_args(argv)
    LOG.info("=== %s 开始 (pid=%s) ===", args.cmd, os.getpid())
    try:
        if args.cmd == "bootstrap":
            return cmd_bootstrap(args)
        if args.cmd == "discover":
            return cmd_discover(args)
        if args.cmd == "run":
            return cmd_run(args)
    except KeyboardInterrupt:
        LOG.warning("已中断")
        return 130
    finally:
        LOG.info("=== %s 结束 ===", args.cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
