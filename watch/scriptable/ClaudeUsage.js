// Claude usage — Scriptable iPhone widget (no Mac, no Xcode).
//
// Setup:
//   1) Install "Scriptable" from the App Store.
//   2) Scriptable -> + (new script) -> paste this whole file.
//   3) Set GIST_URL below to YOUR raw gist url (from: claude_warmup_usage.py publish).
//   4) Home Screen -> add a "Scriptable" widget (Small) -> long-press -> Edit Widget
//      -> Script: ClaudeUsage. Tap the widget to refresh; iOS also refreshes it
//      periodically on its own.

const GIST_URL = "https://gist.githubusercontent.com/<you>/<id>/raw/claude_usage.json"

const CARD_BG = new Color("#1C1C1E")
const TRACK   = new Color("#3A3A3C")
const TXT     = new Color("#F2F2F7")
const MUTED   = new Color("#8E8E93")
const CLAUDE  = new Color("#D97757")
const WEEK    = new Color("#636366")

function levelColor(p) {
  if (p >= 80) return new Color("#FF453A")
  if (p >= 50) return new Color("#FF9F0A")
  return new Color("#30D158")
}

async function getData() {
  try {
    // cache-buster query so GitHub's CDN can't serve a stale copy
    const url = GIST_URL + (GIST_URL.indexOf("?") >= 0 ? "&" : "?") + "t=" + Date.now()
    const req = new Request(url)
    req.headers = { "Cache-Control": "no-cache" }
    const j = await req.loadJSON()
    return {
      five: (j.five_hour && j.five_hour.used_pct) || 0,
      week: (j.seven_day && j.seven_day.used_pct) || 0,
      epoch: j.updated_epoch || Math.floor(Date.now() / 1000),
      ok: true,
    }
  } catch (e) {
    return { five: 0, week: 0, epoch: Math.floor(Date.now() / 1000), ok: false }
  }
}

function rel(epoch) {
  const m = Math.max(0, Math.floor((Date.now() / 1000 - epoch) / 60))
  if (m < 1) return "刚刚"
  if (m < 60) return m + " 分钟前"
  return Math.floor(m / 60) + " 小时前"
}

function barImage(pct, color, w, h) {
  const ctx = new DrawContext()
  ctx.size = new Size(w, h)
  ctx.opaque = false
  ctx.respectScreenScale = true
  const r = h / 2
  const track = new Path()
  track.addRoundedRect(new Rect(0, 0, w, h), r, r)
  ctx.addPath(track); ctx.setFillColor(TRACK); ctx.fillPath()
  const fw = Math.max(h, Math.round((w * Math.min(Math.max(pct, 0), 100)) / 100))
  const fill = new Path()
  fill.addRoundedRect(new Rect(0, 0, fw, h), r, r)
  ctx.addPath(fill); ctx.setFillColor(color); ctx.fillPath()
  return ctx.getImage()
}

function row(parent, label, pct, prominent) {
  const r = parent.addStack()
  r.centerAlignContent()
  const lw = r.addStack(); lw.size = new Size(20, 0)
  const lt = lw.addText(label)
  lt.font = Font.systemFont(prominent ? 13 : 12)
  lt.textColor = prominent ? TXT : MUTED
  lt.lineLimit = 1
  r.addSpacer(5)
  const bw = 58, bh = prominent ? 12 : 6
  const img = r.addImage(barImage(pct, prominent ? levelColor(pct) : WEEK, bw, bh))
  img.imageSize = new Size(bw, bh)
  r.addSpacer(5)
  const vw = r.addStack(); vw.size = new Size(46, 0)
  const vt = vw.addText(pct + "%")
  vt.font = prominent ? Font.semiboldSystemFont(18) : Font.systemFont(13)
  vt.textColor = prominent ? TXT : MUTED
  vt.rightAlignText()
  vt.lineLimit = 1
  vt.minimumScaleFactor = 0.6
}

const d = await getData()

const w = new ListWidget()
w.backgroundColor = CARD_BG
w.setPadding(13, 14, 13, 14)

const head = w.addStack()
head.centerAlignContent()
const sym = SFSymbol.named("sparkles")
sym.applyFont(Font.systemFont(13))
const li = head.addImage(sym.image)
li.imageSize = new Size(15, 15)
li.tintColor = CLAUDE
head.addSpacer(5)
const ht = head.addText(d.ok ? rel(d.epoch) : "无法连接")
ht.font = Font.systemFont(12)
ht.textColor = MUTED
head.addSpacer()

w.addSpacer(10)
row(w, "5h", d.five, true)
w.addSpacer(8)
row(w, "周", d.week, false)

if (config.runsInWidget) {
  Script.setWidget(w)
} else {
  w.presentSmall()
}
Script.complete()
