## HTML reports

- HTML reports for John always use a dark theme (dark background, light
  text; no light-mode variant).
- Always give John a tailnet link, never just a file path. Serve the
  report directory from a loopback HTTP server that keeps running after
  your turn, then publish it on a unique path:
  `nohup python3 -m http.server "$port" --bind 127.0.0.1 --directory "$dir" >/dev/null 2>&1 &`
  and `tailscale serve --bg --https=443 --set-path "/$slug" "http://127.0.0.1:$port"`
  (the macOS Tailscale app can't serve directories directly). The host is
  `tailscale status --json`'s `.Self.DNSName` without the trailing dot
  (not `hostname`). Check that `https://$host/$slug/` returns 200
  (`curl --noproxy '*'`) before sharing it. Leave other Serve mappings
  alone.
