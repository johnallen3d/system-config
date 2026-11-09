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
-- ../../crates/tab-picker/src/main.rs and
-- ../../crates/core/src/actions.rs.
local util = require("switchyard.float")

local label = "tab-picker"

-- One server's rows: host_rows.lua beside this file, which rex-tab-picker
-- also builds in for its standalone mode, run as `rex [-S HOST] do -e SCRIPT
-- host=HOST`, or for the config host `host=local`.
local host_rows_script
do
  local source = debug.getinfo(1, "S").source:gsub("^@", "")
  local path = (source:match("^(.*)/[^/]*$") or ".") .. "/host_rows.lua"
  local file, err = io.open(path, "r")
  if file == nil then error("tab-picker: " .. tostring(err), 0) end
  host_rows_script = file:read("*a")
  file:close()
end

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
