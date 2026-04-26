# Bottombar

A bottom-positioned sketchybar instance for displaying music info (MPV).

## Components

- `sketchybarrc` - Lua entry point that loads the bar configuration
- `items/` - Bar item definitions (music_art, music)
- `plugins/yem-updater` - Background script that queries MPV and updates the bar

## Troubleshooting

### Bar not displaying music info

If the bottombar is not showing music information:

1. **Check if MPV is running with the IPC socket:**
   ```bash
   ls -la /tmp/mpv-music.sock
   ```

2. **Check if the yem-updater is running:**
   ```bash
   pgrep -lf yem-updater
   ```

3. **Manually test MPV communication:**
   ```bash
   echo '{ "command": ["get_property", "path"] }' | socat - /tmp/mpv-music.sock | jq
   ```

### Restarting Services

**Restart MPV music service:**
```bash
launchctl kickstart -k gui/$(id -u)/org.nixos.mpv-music
```

**Restart bottombar:**
```bash
# Kill and let launchd restart it
pkill -f "bottombar"

# Or manually restart
launchctl kickstart -k gui/$(id -u)/org.nixos.bottombar
```

**Restart the yem-updater script:**
```bash
pkill -f yem-updater
# It will be restarted automatically when bottombar reloads
```

### Logs

- MPV stdout: `~/Library/Logs/org.nixos/mpv-music.out.log`
- MPV stderr: `~/Library/Logs/org.nixos/mpv-music.err.log`
- yem-updater: `/tmp/yem-updater.log` (if redirected)
