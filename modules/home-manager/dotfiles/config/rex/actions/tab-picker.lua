-- Pick a tab across sessions and hosts with rex-tab-picker.
-- The float opens at once, waiting; a background `rex do` on the config host
-- lists every server's tabs in parallel (one `rex do` per server, each
-- attaching to all its sessions) and types the rows into the float, which
-- runs on the focused session's host (see util.open_filled_float). The
-- picker records its pick in the terminal title, which the action can read
-- through the session API. Each session gets a header row that picks its
-- current tab.
local util = require("lib.util")

local label = "tab-picker"

-- One server's rows, run as `rex [-S HOST] do host=HOST`, or for the config
-- host `rex do host=local`, which also shows its home as ~. (`rex do` reads
-- an argument value with a slash as a script path and one like 6e6173 as a
-- number, so the script looks up $HOME and hex-encodes the label itself.)
local host_rows_script = [==[
local terminal = "com.superlogical.terminal"
local server, host = rex, rex.args.host
local home = host == "local" and rex.exec({ "sh", "-c", 'printf %s "$HOME"' }).stdout or ""
-- Hex keeps arbitrary host labels safe inside the terminal-title payload.
local target = host == "local" and "-" or host:gsub(".", function(c) return string.format("%02x", c:byte()) end)
local groups = {}
-- Agents report status per pane; a tab shows its most urgent one.
local urgency = { done = 1, working = 2, error = 3, blocked = 4 }
do
  local list, err = server.call("session.list")
  if list == nil then error(host .. ": " .. tostring(err), 0) end
  for _, session in ipairs(list.sessions or {}) do
    local _, attach_err = server.session.attach{ session_id = session.session_id }
    if attach_err ~= nil then error(attach_err, 0) end
    local view, view_err = server.session.view{ session_id = session.session_id }
    if view == nil then error(view_err, 0) end
    local tabs = {}
    groups[#groups + 1] = { session = session, tabs = tabs, host = host, target = target }
    for _, window in ipairs(view.windows or {}) do
      local blocks = {}
      for _, layer in ipairs(window.layers or {}) do
        if layer.kind == "tiled" then
          for _, block in ipairs(layer.blocks or {}) do
            blocks[#blocks + 1] = block.block_id
          end
        end
      end
      local block_id = blocks[1]
      local state
      for _, id in ipairs(blocks) do
        if id == window.focused_block_id then block_id = id end
        local status = server.block.call(terminal, "program_status",
          { session_id = session.session_id, block_id = id })
        for _, record in ipairs((status and status.records) or {}) do
          if (urgency[record.state] or 0) > (urgency[state] or 0) then
            state = record.state
          end
        end
      end
      local args = { session_id = session.session_id, block_id = block_id }
      local name = window.label or ""
      local dir = ""
      if block_id ~= nil then
        local title = server.block.call(terminal, "title", args)
        if name:match("^Window %x+$") and title and title.title ~= "" then
          name = title.title
        end
        local pwd = server.block.call(terminal, "pwd", args)
        dir = ((pwd and pwd.pwd) or ""):gsub("^file://[^/]*", "")
        if home ~= "" and dir:sub(1, #home) == home then
          dir = "~" .. dir:sub(#home + 1)
        end
      end
      tabs[#tabs + 1] = { window_id = window.window_id, name = name, dir = dir, state = state }
    end
  end
end

-- rex-tab-picker draws the rows; see its source for the format.
local function clean(s) return (tostring(s or ""):gsub("[\t\r\n]", " ")) end
local lines = {}
for _, group in ipairs(groups) do
  local session = group.session
  lines[#lines + 1] = table.concat({
    "S", group.target, clean(group.host), session.session_id, clean(session.label or session.session_id),
  }, "\t")
  for _, tab in ipairs(group.tabs) do
    lines[#lines + 1] = table.concat({
      "T", tab.window_id, tab.state or "", clean(tab.name), clean(tab.dir),
    }, "\t")
  end
end
return table.concat(lines, "\n") .. "\n"
]==]

-- The rest of the background script: every server's rows at once, in
-- order (the config host first), delivered together.
local fill_script = "local host_rows_script = " .. string.format("%q", host_rows_script) .. [==[

main(function()
  local jobs = { { host = "local", job = rex.exec.start({ "rex", "do", "-e", host_rows_script, "host=local" }) } }
  for _, host in ipairs(rex.servers()) do
    jobs[#jobs + 1] = { host = host, job = rex.exec.start({ "rex", "-S", host, "do", "-e", host_rows_script,
      "host=" .. host }) }
  end
  local rows = {}
  for _, j in ipairs(jobs) do
    local r = j.job:wait()
    if not r.ok then error(j.host .. ": " .. (r.stderr:gsub("%s+$", "")), 0) end
    rows[#rows + 1] = rex.json.decode(r.stdout)
  end
  deliver("rows", table.concat(rows))
end)
]==]

local function close_picker(ctx) util.close_float(ctx, label) end

-- An action that waits for the picker holds up the app's keys, so this one
-- opens the float and returns. The picker records the highlighted tab, and the
-- tab_picker mode turns Enter and Escape into the actions that finish.
rex.mode("tab_picker")

rex.action{
  name  = "tab_picker",
  title = "Go to Tab…",
  run   = function(ctx, args)
    if util.find_float(ctx, label) ~= nil then return close_picker(ctx) end
    util.open_filled_float(ctx, {
      label    = label,
      mode     = "tab_picker",
      bounds   = { 0.12, 0.1, 0.76, 0.75 },
      command  = util.float_command("rex-tab-picker",
        "--current", ctx.session_id .. "/" .. (ctx.window_id or ""), "--wait"),
      script   = fill_script,
      log_name = "tab-picker.log",
    })
  end,
}

rex.action{
  name  = "tab_picker_go",
  title = "Go to Picked Tab",
  run   = function(ctx, args)
    local _, block_id = util.find_float(ctx, label)
    if block_id == nil or block_id ~= ctx.block_id then
      close_picker(ctx)
      rex.client.queue("pane.send_key", { key = "enter" })
      return
    end
    local pick = rex.block.call("com.superlogical.terminal", "title", {
      session_id = ctx.session_id, block_id = block_id,
    })
    close_picker(ctx)
    local host, session_id, window_id = ((pick and pick.title) or ""):match("^rex%-tab%-picker:([^/]+)/([^/]+)/([^/]*)$")
    if session_id == nil then return end
    if host == "-" then
      rex.client.queue("session.select", {
        session_id = session_id, window_id = window_id ~= "" and window_id or nil,
      })
      return
    end
    util.select_on_host(util.unhex(host), "tab-picker.log", util.cli_env(),
      session_id, window_id ~= "" and window_id or nil)
  end,
}

rex.action{
  name  = "tab_picker_cancel",
  title = "Close Tab Picker",
  run   = function(ctx, args) close_picker(ctx) end,
}

rex.bind("cmd+k", "tab_picker")
rex.bind("tab_picker/enter", "tab_picker_go")
rex.bind("tab_picker/escape", "tab_picker_cancel")
