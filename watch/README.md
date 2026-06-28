# Apple Watch + iPhone widgets

Both read the small JSON that `claude_warmup_usage.py publish` writes to your
secret Gist. Make sure `publish` is running on a schedule first (see the main
README) and grab your raw URL — it looks like:

```
https://gist.githubusercontent.com/<you>/<id>/raw/claude_usage.json
```

There are two front-ends:

| | Needs a Mac? | Glanceable on Home/Face | Refresh button |
|---|---|---|---|
| **iPhone widget** (Scriptable) | **No** | yes (Home Screen) | tap widget = re-run |
| **Apple Watch** (Xcode app + widget) | yes, to build | yes (Smart Stack / face) | yes (watchOS 10+) |

---

## A) iPhone widget — no Mac (5 minutes)

1. Install **Scriptable** from the App Store.
2. Open Scriptable → tap **+** → paste all of [`scriptable/ClaudeUsage.js`](scriptable/ClaudeUsage.js).
3. Change `GIST_URL` at the top to **your** raw URL. Tap **Done**.
4. Go to the Home Screen → long-press → **+** → search **Scriptable** → add the
   **Small** widget → long-press the new widget → **Edit Widget** → **Script** =
   `ClaudeUsage`.
5. Tapping the widget opens Scriptable and refreshes; iOS also refreshes it on its
   own schedule (every few minutes to ~an hour, system-decided).

That's the full-colour card from the mockup, on your iPhone, with zero Xcode.

---

## B) Apple Watch — app + widget (needs a Mac with Xcode)

> Apple requires a Mac + Xcode to build any native watchOS app — there's no way
> around it. With a **free** Apple ID the install **expires after 7 days** (just
> rebuild to renew); a paid Developer account ($99/yr) lasts a year.

### 1. Create the project
1. Install **Xcode** from the Mac App Store.
2. Xcode → **File ▸ New ▸ Project ▸ watchOS ▸ App**. Name it `ClaudeUsageWatch`,
   Interface **SwiftUI**, Language **Swift**. Uncheck extras (tests, etc.).
3. **File ▸ New ▸ Target ▸ watchOS ▸ Widget Extension**. Name it
   `ClaudeUsageWidget`. Uncheck "Include Live Activity". Activate the scheme if asked.

### 2. Add the source files
Delete the template `.swift` files Xcode generated in the app and widget targets,
then drag in the files from [`Sources/`](Sources/) (use *Copy items if needed*) and
set **Target Membership** in the File Inspector (right panel):

| File | Add to target(s) |
|---|---|
| `Sources/Shared/Config.swift` | **both** app + widget |
| `Sources/Shared/UsageData.swift` | **both** app + widget |
| `Sources/Shared/UsageCard.swift` | **both** app + widget |
| `Sources/App/ClaudeUsageApp.swift` | app only |
| `Sources/Widget/ClaudeUsageWidget.swift` | widget only |

(There must be exactly one `@main` per target: the app's is in `ClaudeUsageApp.swift`,
the widget's in `ClaudeUsageWidget.swift`.)

### 3. Configure
- In `Config.swift`, set `gistURL` to **your** raw URL.
- Select the project → for **both** targets set **Minimum Deployments = watchOS 10**.
- **Signing & Capabilities** (both targets): Team = your Apple ID (add it in
  Xcode ▸ Settings ▸ Accounts). Give each target a unique Bundle Identifier
  (e.g. `com.yourname.claudeusage` and `…claudeusage.widget`).

### 4. Build to your watch
1. Pair the watch with the iPhone that's connected to this Mac (or connect over
   Wi-Fi: Xcode ▸ Window ▸ Devices and Simulators).
2. Pick the **ClaudeUsageWatch** scheme and your watch as the run destination → **Run** (⌘R).
3. First time: on the watch/phone, trust the developer cert —
   iPhone **Settings ▸ General ▸ VPN & Device Management ▸ trust**.
4. Add the widget: on the watch, swipe up for the **Smart Stack** → scroll down →
   **Edit** / **＋** → add **Claude 用量**. (Or add it to a watch face slot that
   supports a rectangular accessory.)

### Notes & limitations (please read)
- **Colour on the watch face/Smart Stack is limited.** watchOS renders accessory
  widgets in the face's tint, so the green/amber/red won't show there — the bar
  *length* still conveys usage. The **full-colour** card (exactly the mockup) is
  the **app screen** you get when you open the app; the on-face widget is the
  glanceable, tinted version.
- **Not real-time.** The widget shows the last value the Gist had; it auto-refreshes
  on watchOS's budget (tens of times/day) and when you tap its refresh button. The
  data is only as fresh as your PC's last `publish` (every 30 min).
- **7-day expiry** on free signing — re-run from Xcode to renew.
