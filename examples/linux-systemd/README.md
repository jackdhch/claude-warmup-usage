# Native Linux scheduling (systemd user timers)

For a non‑WSL Linux box. Assumes the repo is at `~/claude-warmup-usage` and you've
finished install + `bootstrap`. Put your Server酱 key in `~/.serverchan_key`.

## Install the user units

```bash
mkdir -p ~/.config/systemd/user
cp examples/linux-systemd/claude-warmup-*.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now claude-warmup-morning.timer
systemctl --user enable --now claude-warmup-auto.timer
systemctl --user list-timers | grep claude   # verify
```

## Run while logged out

User services stop when you log out unless lingering is enabled:

```bash
sudo loginctl enable-linger "$USER"
```

(A headless server is "logged out" by default, so this is usually required.)

## Logs

```bash
journalctl --user -u claude-warmup-auto.service -n 50
tail -f ~/.claude-warmup.log
```

## Cron alternative

If you prefer cron, `crontab -e`:

```cron
# weekday morning warmup
55 6 * * 1-5 ~/claude-warmup-usage/.venv/bin/python ~/claude-warmup-usage/claude_warmup_usage.py run
# hourly auto-activation, 09:00-23:00 every day
0 9-23 * * *  ~/claude-warmup-usage/.venv/bin/python ~/claude-warmup-usage/claude_warmup_usage.py run --auto
```
