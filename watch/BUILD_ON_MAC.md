# Build the Apple Watch app with Claude Code on a Mac

The watch app can't be built on Windows/WSL — Apple requires a Mac + Xcode. The
easiest path is to let **Claude Code on the Mac** scaffold the Xcode project,
compile the Swift in `Sources/`, and fix any errors with real compiler feedback.

## Prerequisites (on the Mac)
1. **Xcode** installed (Mac App Store) and opened once to finish component install.
2. **Claude Code** installed.
3. This repo cloned: `git clone https://github.com/jackdhch/claude-warmup-usage.git`
4. Your **Gist raw URL** (from `claude_warmup_usage.py publish` on your PC).

## Then: open Claude Code in the repo and paste this prompt

> I'm on a Mac with Xcode installed. This repo's `watch/Sources/` has SwiftUI
> sources for a **watch-only watchOS app + a WidgetKit widget** that shows Claude
> usage fetched from a JSON URL. Build a working Xcode project from them and get
> it compiling.
>
> - Create a watchOS **app** target `ClaudeUsageWatch` and a watchOS **Widget
>   Extension** target `ClaudeUsageWidget`; deployment target **watchOS 10**.
> - Target membership:
>   - `Sources/Shared/Config.swift`, `Sources/Shared/UsageData.swift`,
>     `Sources/Shared/UsageCard.swift` → **both** targets
>   - `Sources/App/ClaudeUsageApp.swift` → app target only
>   - `Sources/Widget/ClaudeUsageWidget.swift` → widget target only
> - In `Sources/Shared/Config.swift`, set `gistURL` to:
>   `PASTE_YOUR_GIST_RAW_URL_HERE`
> - Use automatic signing (I'll select my Apple ID team in Xcode). Give the app
>   and widget unique bundle ids (widget id must be prefixed by the app id).
> - Scaffold the project however is most reliable (XcodeGen if handy, otherwise
>   Xcode's own templates). Then run `xcodebuild` for the watch app scheme against
>   a generic watch destination and **fix every compile error until it builds
>   cleanly** — show me what you change. Don't alter the visual design or the JSON
>   parsing.
> - Finally, give me the exact device steps to install on my **physical Apple
>   Watch with a free Apple ID**: pairing/Wi-Fi, selecting my team, trusting the
>   developer cert on the watch, adding the widget to the Smart Stack, and the
>   7-day re-sign caveat. Read `watch/README.md` for design context.

## What you still do by hand (on the devices)
- In Xcode **Settings ▸ Accounts**, add your Apple ID; in each target's
  **Signing & Capabilities**, pick it as the Team.
- Connect/pair the watch, pick it as the run destination, press Run.
- On the iPhone: **Settings ▸ General ▸ VPN & Device Management ▸ trust** the cert.
- On the watch: long-press the face / Smart Stack → add the **Claude 用量** widget.
- Free Apple ID installs expire after **7 days** — just Run again from Xcode to renew.
