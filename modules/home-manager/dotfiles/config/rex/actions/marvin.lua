-- cmd+o: go to the `marvin` tab in the `notes` session on Omarchy. If it isn't
-- open, open it in Omarchy's ~/notes running Claude Code on Haiku at high
-- effort, then show it. A new notes session is placed first.
--
-- An action can only view (or add windows to) sessions its connection is
-- attached to, so the find-or-open runs as a `rex -S omarchy do` script that
-- attaches to the notes session first, the same way switchyard's tab picker
-- does, and the jump goes through Omarchy's app connection.
local util = require("switchyard.float")

local HOST = "omarchy"
local SESSION = "notes"
local LABEL = "marvin"
-- `rex -S` runs the script below here and only its calls on the host, so
-- the pane itself changes to the host's ~/notes.
local COMMAND = { "sh", "-c", 'cd "$HOME/notes" && exec "$@"', "sh" }
for _, arg in ipairs(util.float_command("claude", "--model", "haiku", "--effort", "high")) do
  COMMAND[#COMMAND + 1] = arg
end

local SCRIPT = string.format([==[
local SESSION, LABEL, COMMAND = %q, %q, %q
COMMAND = rex.json.decode(COMMAND)

local list, list_err = rex.call("session.list")
if list == nil then error(list_err, 0) end
local notes
for _, session in ipairs(list.sessions or {}) do
  if session.label == SESSION then notes = session.session_id break end
end
if notes == nil then
  -- No notes session yet: create it with the marvin tab as its only window.
  local created, create_err = rex.call("session.create", {
    label = SESSION,
    initial_windows = { { window_label = LABEL, layout = rex.layout.block{
      flavor  = "com.superlogical.terminal.shell",
      label   = LABEL,
      options = { command = COMMAND },
    } } },
  })
  if created == nil then error(create_err, 0) end
  -- A new session goes last; put it first. Best effort: it still opens.
  local before = (list.sessions or {})[1]
  -- Moving needs this connection attached; session.create doesn't attach.
  if before ~= nil then
    local _, attach_err = rex.session.attach{ session_id = created.session_id }
    if attach_err == nil then
      rex.call("session.move", { session_id = created.session_id, before_session_id = before.session_id })
    end
  end
  local first = (created.initial_windows or {})[1] or {}
  return rex.json.encode({ session_id = created.session_id, window_id = first.window_id })
end

local _, attach_err = rex.session.attach{ session_id = notes }
if attach_err ~= nil then error(attach_err, 0) end
local view, view_err = rex.session.view{ session_id = notes }
if view == nil then error(view_err, 0) end
for _, window in ipairs(view.windows or {}) do
  if window.label == LABEL then
    return rex.json.encode({ session_id = notes, window_id = window.window_id })
  end
end

local window, err = rex.session.new_window{
  session_id   = notes,
  window_label = LABEL,
  focus        = true,
  layout       = rex.layout.block{
    flavor  = "com.superlogical.terminal.shell",
    label   = LABEL,
    options = { command = COMMAND },
  },
}
if window == nil then error(err, 0) end
return rex.json.encode({ session_id = notes, window_id = window.window_id })
]==], SESSION, LABEL, rex.json.encode(COMMAND))

-- `rex do` prints the returned string as JSON.
local function decode_tab(output)
  local ok, out = pcall(rex.json.decode, output)
  if ok and type(out) == "string" then ok, out = pcall(rex.json.decode, out) end
  if not ok or type(out) ~= "table" or out.session_id == nil then
    error("can't read the marvin tab from: " .. output, 0)
  end
  return out
end

rex.action{
  name  = "marvin_open",
  title = "Go to marvin (notes)",
  run   = function(ctx, args)
    local env = util.cli_env()
    local r, err = rex.exec({ "rex", "-S", HOST, "do", "-e", SCRIPT }, { env = env })
    if r == nil then error(err, 0) end
    if not r.ok then error((r.stderr:gsub("%s+$", "")), 0) end
    local tab = decode_tab(r.stdout)
    util.select_on_host(HOST, "marvin.log", env, tab.session_id, tab.window_id)
  end,
}

rex.bind("cmd+o", "marvin_open")
