# Build the Apple Watch app with Claude Code on a Mac

The watch app can't be built on Windows/WSL — Apple requires a Mac + Xcode. The
easiest path is to let **Claude Code on the Mac** clone the repo, scaffold the
Xcode project, compile the Swift in `Sources/`, and fix any errors with real
compiler feedback.

## Prerequisites (on the Mac)
1. **Xcode** installed (Mac App Store), opened once to finish component install.
2. **Claude Code** installed.
3. Your **Gist raw URL** (from `claude_warmup_usage.py publish` on your PC).

## Open Claude Code anywhere and paste this prompt

> Do everything from clone to compile, don't wait for me:
>
> 1) Clone the repo into my home dir: `cd ~`; if `~/claude-warmup-usage` exists but
>    is incomplete, `rm -rf` it first; run
>    `git clone https://github.com/jackdhch/claude-warmup-usage.git`. If it fails
>    with an "HTTP2 framing layer" error, run `git config --global http.version
>    HTTP/1.1` and retry; if still failing, use SSH
>    `git@github.com:jackdhch/claude-warmup-usage.git`. Then `cd ~/claude-warmup-usage`.
>
> 2) `watch/Sources/` has SwiftUI sources for a **watch-only watchOS app + a
>    WidgetKit widget** that shows Claude usage from a JSON URL. Build a working
>    Xcode project from them and get it compiling:
>    - App target `ClaudeUsageWatch` + Widget Extension target `ClaudeUsageWidget`;
>      deployment target **watchOS 10**.
>    - Target membership: `Sources/Shared/Config.swift`, `UsageData.swift`,
>      `UsageCard.swift` → **both** targets; `Sources/App/ClaudeUsageApp.swift` →
>      app only; `Sources/Widget/ClaudeUsageWidget.swift` → widget only.
>    - Set `gistURL` in `Sources/Shared/Config.swift` to `PASTE_YOUR_GIST_RAW_URL`.
>    - Automatic signing (I'll pick my Apple ID team in Xcode); unique bundle ids
>      (widget id prefixed by app id).
>    - Scaffold however is most reliable (XcodeGen if handy, else Xcode templates).
>      Run `xcodebuild` on the watch app scheme and **fix every compile error until
>      it builds cleanly** — show me what you change. Don't alter the visual design
>      or JSON parsing.
>
> 3) Then give me the exact steps to install on my **physical Apple Watch with a
>    free Apple ID**: pairing/Wi-Fi, selecting my team, trusting the cert on the
>    watch, adding the **Claude 用量** widget to the Smart Stack, and the 7-day
>    re-sign caveat. See `watch/README.md` for design context.

## What you still do by hand (on the devices)
- In Xcode **Settings ▸ Accounts** add your Apple ID; pick it as Team in each
  target's **Signing & Capabilities**.
- Connect/pair the watch, choose it as run destination, press Run.
- iPhone **Settings ▸ General ▸ VPN & Device Management ▸ trust** the cert.
- Watch: long-press the face / Smart Stack → add the **Claude 用量** widget.
- Free Apple ID installs expire after **7 days** — Run again from Xcode to renew.
