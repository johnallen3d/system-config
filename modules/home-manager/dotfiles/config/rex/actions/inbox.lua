-- The cmd+i task inbox: work spawned with ctrl+cmd+n, on every host, with the
-- tasks that need John first. The float opens at once, waiting; a
-- background job on the config host, which holds the task registry and
-- reaches every Rex host, types the tasks into it (see
-- util.open_filled_float): first `rex-spawn --tasks --live`, the registry
-- with each tab's live agent status from Rex, then `rex-spawn --tasks`, which
-- also checks each task's worktree over SSH and ends the gone ones. The
-- float, which may run on another host, reports the highlighted task in its terminal title, and the
-- inbox mode turns Enter into the jump (or an archive armed with ctrl+x in the
-- float, with an extra "are you sure" Enter when that throws away uncommitted
-- changes) and ctrl+r into review. In the float's archive view (ctrl+a),
-- Enter resumes the ended task's agent session in a new tab on its host and
-- jumps there. See packages/rex-spawn/src/inbox.rs and actions.rs.
local util = require("lib.util")

local label = "rex-inbox"

local function close_inbox(ctx) util.close_float(ctx, label) end

-- The rest of the background script that fills the float.
local fill_script = [==[
main(function()
  for _, step in ipairs({ { "live", "--live" }, { "tasks" } }) do
    local r, err = rex.exec({ "rex-spawn", "--tasks", step[2] })
    if r == nil then error(err, 0) end
    if not r.ok then error((r.stderr:gsub("^rex%-spawn: ", "")), 0) end
    deliver(step[1], r.stdout)
  end
end)
]==]

local function host_label()
  return (rex.exec({ "hostname", "-s" }).stdout:gsub("%s+$", ""))
end

rex.mode("inbox")

rex.action{
  name  = "inbox",
  title = "Task Inbox…",
  run   = function(ctx, args)
    if util.find_float(ctx, label) ~= nil then return close_inbox(ctx) end
    -- Start on the current tab's task. Key actions carry no window_id, so
    -- fall back to the session's active tab.
    local view = ctx.window_id == nil and rex.session.view{ session_id = ctx.session_id } or nil
    local current = ctx.session_id .. "/" .. (ctx.window_id or (view and view.active_window_id) or "")
    util.open_filled_float(ctx, {
      label    = label,
      mode     = "inbox",
      bounds   = { 0.12, 0.12, 0.76, 0.6 },
      command  = util.float_command("rex-spawn", "--inbox", "-", current),
      script   = fill_script,
      log_name = "inbox.log",
    })
  end,
}

-- The float's pick: action ("go", "resume", or an armed "archive", "ask" or "force-archive"), host, session and
-- window. Keys pressed with the float not focused fall through to the pane.
local function read_pick(ctx, key)
  local _, block_id = util.find_float(ctx, label)
  if block_id == nil or block_id ~= ctx.block_id then
    close_inbox(ctx)
    rex.client.queue("pane.send_key", { key = key })
    return nil
  end
  local pick = rex.block.call("com.superlogical.terminal", "title", {
    session_id = ctx.session_id, block_id = block_id,
  })
  local action, host, session_id, window_id = ((pick and pick.title) or "")
    :match("^rex%-spawn%-inbox:([%a%-]+):(%x+)/([^/]+)/([^/]+)$")
  if action == nil then return nil end
  return { action = action, host = util.unhex(host), session_id = session_id, window_id = window_id,
    float = block_id }
end

local function jump(pick)
  if pick.host == host_label() then
    rex.client.queue("session.select", { session_id = pick.session_id, window_id = pick.window_id })
    return
  end
  util.select_on_host(pick.host, "inbox.log", util.cli_env(), pick.session_id, pick.window_id)
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
  name  = "inbox_go",
  title = "Go to, Archive or Resume Picked Task",
  run   = function(ctx, args)
    local pick = read_pick(ctx, "enter")
    -- Nothing picked (empty inbox); keep the float open.
    if pick == nil then return end
    -- A dirty worktree: keep the float open and type ctrl-x into it, which
    -- moves it on to "are you sure"; the next Enter answers force-archive.
    if pick.action == "ask" then
      rex.block.call("com.superlogical.terminal", "write", {
        session_id = ctx.session_id, block_id = pick.float, data = "\24",
      })
      return
    end
    close_inbox(ctx)
    if pick.action == "archive" or pick.action == "force-archive" then return act(pick.action, pick) end
    if pick.action == "resume" then return resume(pick) end
    jump(pick)
  end,
}

-- Review opens lazygit beside the highlighted task's agent, then shows its tab.
rex.action{
  name  = "inbox_review",
  title = "Review Picked Task",
  run   = function(ctx, args)
    local pick = read_pick(ctx, "ctrl+r")
    -- Ended tasks have nothing to review.
    if pick == nil or pick.action == "resume" then return end
    close_inbox(ctx)
    act("review", pick)
    jump(pick)
  end,
}

rex.action{
  name  = "inbox_cancel",
  title = "Close Task Inbox",
  run   = function(ctx, args) close_inbox(ctx) end,
}

rex.bind("cmd+i", "inbox")
rex.bind("inbox/enter", "inbox_go")
rex.bind("inbox/ctrl+r", "inbox_review")
rex.bind("inbox/escape", "inbox_cancel")
