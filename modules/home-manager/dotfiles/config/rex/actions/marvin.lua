-- cmd+o: go to the `marvin` tab in the `notes` session. If it isn't open, open
-- it in ~/notes running Claude Code on Haiku at high effort, then show it.
--
-- An action can only view (or add windows to) sessions its connection is
-- attached to, so the find-or-open runs as a `rex do` script that attaches to
-- the notes session first, the same way switchyard's tab picker does.
local util = require("switchyard.float")

local SESSION = "notes"
local LABEL = "marvin"
local CWD = (os.getenv("HOME") or "") .. "/notes"
local COMMAND = util.float_command("claude", "--model", "haiku", "--effort", "high")

local SCRIPT = string.format([==[
local SESSION, LABEL, CWD, COMMAND = %q, %q, %q, %q
COMMAND = rex.json.decode(COMMAND)

local list, list_err = rex.call("session.list")
if list == nil then error(list_err, 0) end
local notes
for _, session in ipairs(list.sessions or {}) do
  if session.label == SESSION then notes = session.session_id break end
end
if notes == nil then error("no session labelled " .. SESSION, 0) end

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
    options = { command = COMMAND, cwd = CWD },
  },
}
if window == nil then error(err, 0) end
return rex.json.encode({ session_id = notes, window_id = window.window_id })
]==], SESSION, LABEL, CWD, rex.json.encode(COMMAND))

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
    local r, err = rex.exec({ "rex", "do", "-e", SCRIPT }, { env = util.cli_env() })
    if r == nil then error(err, 0) end
    if not r.ok then error((r.stderr:gsub("%s+$", "")), 0) end
    local tab = decode_tab(r.stdout)
    rex.client.queue("session.select", { session_id = tab.session_id, window_id = tab.window_id })
  end,
}

rex.bind("cmd+o", "marvin_open")
