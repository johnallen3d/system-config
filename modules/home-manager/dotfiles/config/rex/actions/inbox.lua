-- The cmd+i task inbox: work spawned with ctrl+cmd+n, on every host, with the
-- tasks that need John first. `rex-spawn --tasks` runs here on the config
-- host, which holds the task registry and reaches every Rex host; it checks
-- each task's tab and worktree and adds the tab's live agent status. Its JSON
-- goes to the float, which may run on another host, as the tab picker's rows
-- do. The float reports the highlighted task in its terminal title, and the
-- inbox mode turns Enter into the jump (or a discard armed with ctrl+x in the
-- float, with an extra "are you sure" Enter when that throws away uncommitted
-- changes) and ctrl+r into review. See
-- packages/rex-spawn/src/inbox.rs and actions.rs.
local util = require("lib.util")

local label = "rex-inbox"

local function close_inbox(ctx) util.close_float(ctx, label) end

local function host_label()
  return (rex.exec({ "hostname", "-s" }).stdout:gsub("%s+$", ""))
end

rex.mode("inbox")

rex.action{
  name  = "inbox",
  title = "Task Inbox…",
  run   = function(ctx, args)
    if util.find_float(ctx, label) ~= nil then return close_inbox(ctx) end
    local r, err = rex.exec({ "rex-spawn", "--tasks" }, { env = util.cli_env() })
    if r == nil then error(err, 0) end
    if not r.ok then error(r.stderr, 0) end
    -- Start on the current tab's task. Key actions carry no window_id, so
    -- fall back to the session's active tab.
    local view = ctx.window_id == nil and rex.session.view{ session_id = ctx.session_id } or nil
    local current = ctx.session_id .. "/" .. (ctx.window_id or (view and view.active_window_id) or "")
    local _, layer_err = rex.session.new_layer{
      session_id = ctx.session_id,
      bounds     = { 0.12, 0.12, 0.76, 0.6 },
      focus      = true,
      layout     = rex.layout.block{
        flavor  = "com.superlogical.terminal.shell",
        label   = label,
        options = { command = util.float_command("rex-spawn", "--inbox", r.stdout, current) },
      },
    }
    if layer_err ~= nil then error(layer_err, 0) end
    rex.client.queue("client.mode.enter", { name = "inbox" })
  end,
}

-- The float's pick: action ("go", or an armed "discard", "ask" or "force-discard"), host, session and
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

-- Run `rex-spawn --act` for the pick; a refusal (such as a dirty worktree)
-- comes back as the action's error.
local function act(action, pick)
  local r, err = rex.exec({ "rex-spawn", "--act", action, pick.host, pick.session_id, pick.window_id },
    { env = util.cli_env() })
  if r == nil then error(err, 0) end
  if not r.ok then error((r.stderr:gsub("^rex%-spawn: ", "")), 0) end
end

rex.action{
  name  = "inbox_go",
  title = "Go to or Discard Picked Task",
  run   = function(ctx, args)
    local pick = read_pick(ctx, "enter")
    -- Nothing picked (empty inbox); keep the float open.
    if pick == nil then return end
    -- A dirty worktree: keep the float open and type ctrl-x into it, which
    -- moves it on to "are you sure"; the next Enter answers force-discard.
    if pick.action == "ask" then
      rex.block.call("com.superlogical.terminal", "write", {
        session_id = ctx.session_id, block_id = pick.float, data = "\24",
      })
      return
    end
    close_inbox(ctx)
    if pick.action == "discard" or pick.action == "force-discard" then return act(pick.action, pick) end
    jump(pick)
  end,
}

-- Review opens lazygit beside the highlighted task's agent, then shows its tab.
rex.action{
  name  = "inbox_review",
  title = "Review Picked Task",
  run   = function(ctx, args)
    local pick = read_pick(ctx, "ctrl+r")
    if pick == nil then return end
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
