# Switchyard's MCP endpoint (switchyard-server on the Mac): loopback and
# tailnet peers only, no token. Every agent profile on every host uses it.
# The Rex headers let spawn_task nest new tasks under the caller's tab; the
# server ignores blank values and values starting with "$".
{
  url = "http://johns-macbook-pro.taila14c2.ts.net:7391/mcp";
  # Claude Code: ${VAR:-} sends a blank header when Rex isn't present.
  claudeHeaders = {
    "X-Rex-Session" = "\${REX_SESSION:-}";
    "X-Rex-Block" = "\${REX_BLOCK:-}";
  };
  # Pi fails a server whose header resolves empty, so a shell command
  # falls back to the literal placeholder outside Rex.
  piHeaders = {
    "X-Rex-Session" = "!printf '%s' \"\${REX_SESSION:-\\\${REX_SESSION\\}}\"";
    "X-Rex-Block" = "!printf '%s' \"\${REX_BLOCK:-\\\${REX_BLOCK\\}}\"";
  };
}
