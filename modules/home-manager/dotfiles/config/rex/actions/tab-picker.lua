-- The cmd+k picker: every tab across sessions and hosts, the agents among
-- them, and ended tasks, in one rex-tab-picker float (cmd+i opens it on the
-- agents view). The float opens at once, waiting, on the focused session's
-- host; a background `rex do` on the config host fills it (see
-- util.open_filled_float), running at once:
--
-- - one `rex do` per server listing its tabs (each attaching to all its
--   sessions), delivered together as `rows` (or `error`);
-- - `rex-spawn --tasks --live`, the task registry with each tab's live agent
--   status (`live`), and `rex-spawn --tasks`, which also checks each task's
--   worktree over SSH and ends the gone ones (`tasks`); a registry failure
--   is `tasks-error`, and the float shows tabs only.
--
-- The picker records its pick in the terminal title as
-- rex-tab-picker:ACTION:TARGET/SESSION/WINDOW, which the tab_picker mode
-- reads: Enter jumps (go, task), resumes an ended task's agent session in a
-- new tab and jumps there (resume), or runs an archive armed with ctrl+x in
-- the float (archive, force-archive; for ask, a dirty worktree, it types
-- ctrl+x back so the float asks "are you sure"); ctrl+r reviews a task.
-- TARGET is "-" for this host or the hex-encoded host label. See
-- packages/switchyard/crates/tab-picker/src/main.rs and
-- crates/core/src/actions.rs.
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

-- The rest of the background script. The tab listings and the task fetches
-- start together; rows go out first, then the tasks as they come.
local fill_script = "local host_rows_script = " .. string.format("%q", host_rows_script) .. [==[

main(function()
  local jobs = { { host = "local", job = rex.exec.start({ "rex", "do", "-e", host_rows_script, "host=local" }) } }
  for _, host in ipairs(rex.servers()) do
    jobs[#jobs + 1] = { host = host, job = rex.exec.start({ "rex", "-S", host, "do", "-e", host_rows_script,
      "host=" .. host }) }
  end
  local steps = {}
  for _, step in ipairs({ { "live", "--live" }, { "tasks" } }) do
    local job, err = rex.exec.start({ "rex-spawn", "--tasks", step[2] })
    steps[#steps + 1] = { kind = step[1], job = job, err = err }
  end
  local rows, failed = {}, nil
  for _, j in ipairs(jobs) do
    local r = j.job:wait()
    if not r.ok then failed = failed or (j.host .. ": " .. (r.stderr:gsub("%s+$", ""))) end
    rows[#rows + 1] = r.ok and rex.json.decode(r.stdout) or ""
  end
  if failed then deliver("error", failed) else deliver("rows", table.concat(rows)) end
  for _, step in ipairs(steps) do
    local r = step.job and step.job:wait()
    if r == nil then
      deliver("tasks-error", tostring(step.err or "can't run rex-spawn"))
    elseif not r.ok then
      deliver("tasks-error", (r.stderr:gsub("^rex%-spawn: ", "")))
    else
      deliver(step.kind, r.stdout)
    end
  end
end)
]==]

local function close_picker(ctx) util.close_float(ctx, label) end

local function host_label()
  return (rex.exec({ "hostname", "-s" }).stdout:gsub("%s+$", ""))
end

-- An action that waits for the picker holds up the app's keys, so this one
-- opens the float and returns. The picker records the highlighted row, and
-- the tab_picker mode turns Enter, ctrl+r and Escape into the actions that
-- finish. A second press of either shortcut closes the float.
rex.mode("tab_picker")

local function open_picker(ctx, view)
  if util.find_float(ctx, label) ~= nil then return close_picker(ctx) end
  -- Start on the current tab. Key actions carry no window_id, so fall back
  -- to the session's active tab.
  local session_view = ctx.window_id == nil and rex.session.view{ session_id = ctx.session_id } or nil
  local current = ctx.session_id .. "/" .. (ctx.window_id or (session_view and session_view.active_window_id) or "")
  util.open_filled_float(ctx, {
    label    = label,
    mode     = "tab_picker",
    bounds   = { 0.12, 0.1, 0.76, 0.75 },
    command  = util.float_command("rex-tab-picker", "--current", current, "--view", view, "--wait"),
    script   = fill_script,
    log_name = "tab-picker.log",
  })
end

rex.action{
  name  = "tab_picker",
  title = "Go to Tab…",
  run   = function(ctx, args) open_picker(ctx, "all") end,
}

rex.action{
  name  = "tab_picker_agents",
  title = "Agents…",
  run   = function(ctx, args) open_picker(ctx, "agents") end,
}

-- The float's pick: action, host (the config host's label for "-"),
-- session and window. Keys pressed with the float not focused fall through
-- to the pane.
local function read_pick(ctx, key)
  local _, block_id = util.find_float(ctx, label)
  if block_id == nil or block_id ~= ctx.block_id then
    close_picker(ctx)
    rex.client.queue("pane.send_key", { key = key })
    return nil
  end
  local pick = rex.block.call("com.superlogical.terminal", "title", {
    session_id = ctx.session_id, block_id = block_id,
  })
  local action, target, session_id, window_id = ((pick and pick.title) or "")
    :match("^rex%-tab%-picker:([%a%-]+):([^/]+)/([^/]+)/([^/]+)$")
  if action == nil then return nil end
  local here = target == "-"
  return { action = action, host = here and host_label() or util.unhex(target), here = here,
    session_id = session_id, window_id = window_id, float = block_id }
end

local function jump(pick)
  if pick.here or pick.host == host_label() then
    rex.client.queue("session.select", { session_id = pick.session_id, window_id = pick.window_id })
    return
  end
  util.select_on_host(pick.host, "tab-picker.log", util.cli_env(), pick.session_id, pick.window_id)
end

-- Run `rex-spawn --act` for the pick and return its output; a refusal (such
-- as a dirty worktree) comes back as the action's error.
local function act(action, pick)
  local r, err = rex.exec({ "rex-spawn", "--act", action, pick.host, pick.session_id, pick.window_id },
    { env = util.cli_env() })
  if r == nil then error(err, 0) end
  if not r.ok then error((r.stderr:gsub("^rex%-spawn: ", "")), 0) end
  return r.stdout
end

-- Resume prints the new tab as HOST<TAB>SESSION_ID<TAB>WINDOW_ID.
local function resume(pick)
  local host, session_id, window_id = act("resume", pick):match("^([^\t]+)\t([^\t]+)\t([^\t\n]+)")
  if host == nil then error("rex-spawn --act resume printed no tab", 0) end
  jump({ host = host, session_id = session_id, window_id = window_id })
end

rex.action{
  name  = "tab_picker_go",
  title = "Go to, Archive or Resume Picked Row",
  run   = function(ctx, args)
    local pick = read_pick(ctx, "enter")
    -- Nothing picked (an empty list); keep the float open.
    if pick == nil then return end
    -- A dirty worktree: keep the float open and type ctrl-x into it, which
    -- moves it on to "are you sure"; the next Enter answers force-archive.
    if pick.action == "ask" then
      rex.block.call("com.superlogical.terminal", "write", {
        session_id = ctx.session_id, block_id = pick.float, data = "\24",
      })
      return
    end
    close_picker(ctx)
    if pick.action == "archive" or pick.action == "force-archive" then return act(pick.action, pick) end
    if pick.action == "resume" then return resume(pick) end
    jump(pick)
  end,
}

-- Review opens lazygit beside the highlighted task's agent, then shows its tab.
rex.action{
  name  = "tab_picker_review",
  title = "Review Picked Task",
  run   = function(ctx, args)
    local pick = read_pick(ctx, "ctrl+r")
    -- Only open tasks have something to review.
    if pick == nil or pick.action ~= "task" then return end
    close_picker(ctx)
    act("review", pick)
    jump(pick)
  end,
}

rex.action{
  name  = "tab_picker_cancel",
  title = "Close Tab Picker",
  run   = function(ctx, args) close_picker(ctx) end,
}

rex.bind("cmd+k", "tab_picker")
rex.bind("cmd+i", "tab_picker_agents")
rex.bind("tab_picker/enter", "tab_picker_go")
rex.bind("tab_picker/ctrl+r", "tab_picker_review")
rex.bind("tab_picker/escape", "tab_picker_cancel")
