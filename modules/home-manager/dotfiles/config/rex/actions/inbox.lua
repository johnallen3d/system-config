-- The cmd+i task inbox: work spawned with ctrl+cmd+n, on every host, with the
-- tasks that need John first. `rex-spawn --tasks` runs here on the config
-- host, which holds the task registry and reaches every Rex host; it checks
-- each task's tab and worktree and adds the tab's live agent status. Its JSON
-- goes to the float, which may run on another host, as the tab picker's rows
-- do. The float reports the highlighted task in its terminal title, and the
-- inbox mode turns Enter into the jump. See packages/rex-spawn/src/inbox.rs.
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
    local _, layer_err = rex.session.new_layer{
      session_id = ctx.session_id,
      bounds     = { 0.12, 0.12, 0.76, 0.6 },
      focus      = true,
      layout     = rex.layout.block{
        flavor  = "com.superlogical.terminal.shell",
        label   = label,
        options = { command = util.float_command("rex-spawn", "--inbox", r.stdout) },
      },
    }
    if layer_err ~= nil then error(layer_err, 0) end
    rex.client.queue("client.mode.enter", { name = "inbox" })
  end,
}

rex.action{
  name  = "inbox_go",
  title = "Go to Picked Task",
  run   = function(ctx, args)
    local _, block_id = util.find_float(ctx, label)
    if block_id == nil or block_id ~= ctx.block_id then
      close_inbox(ctx)
      rex.client.queue("pane.send_key", { key = "enter" })
      return
    end
    local pick = rex.block.call("com.superlogical.terminal", "title", {
      session_id = ctx.session_id, block_id = block_id,
    })
    local host, session_id, window_id = ((pick and pick.title) or "")
      :match("^rex%-spawn%-inbox:(%x+)/([^/]+)/([^/]+)$")
    -- Nothing to go to (empty inbox or no match); keep the float open.
    if host == nil then return end
    close_inbox(ctx)
    host = util.unhex(host)
    if host == host_label() then
      rex.client.queue("session.select", { session_id = session_id, window_id = window_id })
      return
    end
    util.select_on_host(host, "inbox.log", util.cli_env(), session_id, window_id)
  end,
}

rex.action{
  name  = "inbox_cancel",
  title = "Close Task Inbox",
  run   = function(ctx, args) close_inbox(ctx) end,
}

rex.bind("cmd+i", "inbox")
rex.bind("inbox/enter", "inbox_go")
rex.bind("inbox/escape", "inbox_cancel")
