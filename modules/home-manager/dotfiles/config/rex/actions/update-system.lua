-- cmd+shift+u: open a new `update-system` tab in this Mac's system-config
-- session (creating the session if there is none), run `mise update-system`
-- in ~/dev/src/system-config, then show the tab. The tab closes when the
-- update succeeds; on failure a login shell stays open so the output can be read.
--
-- Server actions see only the focused session's server, so the find-or-open
-- runs as a local `rex do` script (as yem.lua does) and the jump is queued on
-- this Mac's app, which owns queued client actions even from remote sessions.
local util = require("switchyard.float")

local SESSION = "system-config"
local LABEL = "update-system"
local COMMAND = {
  "sh", "-c",
  'PATH="$HOME/.local/bin:/etc/profiles/per-user/$(id -un)/bin:/opt/homebrew/bin:$PATH"; export PATH; '
    .. 'cd "$HOME/dev/src/system-config" && mise update-system || exec "${SHELL:-fish}" -l',
}

local SCRIPT = string.format([==[
local SESSION, LABEL, COMMAND = %q, %q, rex.json.decode(%q)
local layout = rex.layout.block{
  flavor  = "com.superlogical.terminal.shell",
  label   = LABEL,
  options = { command = COMMAND },
}

local list, list_err = rex.call("session.list")
if list == nil then error(list_err, 0) end
local target
for _, session in ipairs(list.sessions or {}) do
  if session.label == SESSION then target = session.session_id break end
end

if target == nil then
  local created, err = rex.call("session.create", {
    label = SESSION,
    initial_windows = { { window_label = LABEL, layout = layout } },
  })
  if created == nil then error(err, 0) end
  local first = (created.initial_windows or {})[1] or {}
  return { session_id = created.session_id, window_id = first.window_id }
end

local _, attach_err = rex.session.attach{ session_id = target }
if attach_err ~= nil then error(attach_err, 0) end
local window, err = rex.session.new_window{
  session_id = target, window_label = LABEL, focus = true, layout = layout,
}
if window == nil then error(err, 0) end
return { session_id = target, window_id = window.window_id }
]==], SESSION, LABEL, rex.json.encode(COMMAND))

rex.action{
  name  = "update_system",
  title = "Run mise update-system (system-config)",
  run   = function(ctx, args)
    local r, err = rex.exec({ "rex", "--timeout", "10s", "do", "-e", SCRIPT }, { env = util.cli_env() })
    if r == nil then error(err, 0) end
    if not r.ok then error((r.stderr:gsub("%s+$", "")), 0) end
    local tab = rex.json.decode(r.stdout)
    rex.client.queue("session.select", { session_id = tab.session_id, window_id = tab.window_id })
  end,
}

rex.bind("cmd+shift+u", "update_system")
