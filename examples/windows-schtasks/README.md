# Windows (WSL) scheduling via Task Scheduler

These tasks run the warmup script inside WSL on a schedule.

## Quick start

1. Clone this repo inside WSL and finish install + `bootstrap` (see the main README).
2. Edit the variables at the top of [`setup-tasks.ps1`](setup-tasks.ps1)
   (`$Distro`, `$RepoWslPath`, `$MorningTime`).
3. In a normal **PowerShell** window (no admin needed):
   ```powershell
   .\setup-tasks.ps1
   ```

This registers:

| Task | When | Action | Wakes PC |
|---|---|---|---|
| `ClaudeWarmup_Morning` | weekdays at `$MorningTime` | `run` (proactive) | yes |
| `ClaudeWarmup_Auto` | daily, hourly 09:00–24:00 | `run --auto` | no |

## Notes

- **LogonType is `InteractiveToken`** → tasks run when you are logged in (a locked
  screen is fine). WSL itself needs your user session, so "run while fully logged
  out" isn't reliable anyway. To attempt it without storing a password, change
  `InteractiveToken` → `S4U` (requires registering from an **admin** PowerShell).
- Manage tasks:
  ```powershell
  schtasks /Query  /TN ClaudeWarmup_Auto /V /FO LIST
  schtasks /Run    /TN ClaudeWarmup_Auto
  schtasks /Delete /TN ClaudeWarmup_Auto /F
  ```
- Restrict `Auto` to weekdays: edit the trigger in `setup-tasks.ps1`
  (`ScheduleByDay` → `ScheduleByWeek` with Mon–Fri) and re‑run.
