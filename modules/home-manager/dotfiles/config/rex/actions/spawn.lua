-- Spawn agent work with rex-spawn: a catalog project, a work name and an
-- optional work item (recorded in rex-spawn's task registry); the
-- host defaults to the least busy dev machine and the harness to Claude. The
-- picker runs in a float on the focused session's host and reports its
-- choice in the terminal title; Enter launches from this
-- config host, the only one that can reach every Rex host. The new tab runs
-- `rex-spawn --run` on the target host, which makes the worktree with wt and
-- starts the agent there. See packages/rex-spawn/src/main.rs.
local util = require("lib.util")

local label = "rex-spawn"

local function close_picker(ctx) util.close_float(ctx, label) end

local function host_label()
  return (rex.exec({ "hostname", "-s" }).stdout:gsub("%s+$", ""))
end

rex.mode("spawn")

rex.action{
  name  = "spawn",
  title = "Spawn Agent Work…",
  run   = function(ctx, args)
    if util.find_float(ctx, label) ~= nil then return close_picker(ctx) end
    local _, err = rex.session.new_layer{
      session_id = ctx.session_id,
      bounds     = { 0.12, 0.08, 0.76, 0.8 },
      focus      = true,
      layout     = rex.layout.block{
        flavor  = "com.superlogical.terminal.shell",
        label   = label,
        options = { command = util.float_command("rex-spawn", "--local", host_label()) },
      },
    }
    if err ~= nil then error(err, 0) end
    rex.client.queue("client.mode.enter", { name = "spawn" })
  end,
}

rex.action{
  name  = "spawn_go",
  title = "Spawn Picked Work",
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
    local host, path, name, harness, work = ((pick and pick.title) or "")
      :match("^rex%-spawn:(%x+)/(%x+)/(%x+)/(%a+)/(%x*)$")
    -- An incomplete form reports nothing; keep the float open.
    if host == nil then return end
    close_picker(ctx)
    host = util.unhex(host)
    local env = util.cli_env()
    local r, err = rex.exec({ "rex-spawn", "--launch", host, util.unhex(path), util.unhex(name), harness,
      util.unhex(work) },
      { env = env })
    if r == nil then error(err, 0) end
    if not r.ok then error(r.stderr, 0) end
    -- With host "auto", --launch picks the host and reports it first.
    local session_id, window_id
    host, session_id, window_id = r.stdout:match("^(%S+)\t(%S+)\t(%S+)$")
    if session_id == nil then error("rex-spawn: unexpected launch output: " .. r.stdout, 0) end
    if host == host_label() then
      rex.client.queue("session.select", { session_id = session_id, window_id = window_id })
      return
    end
    util.select_on_host(host, "spawn.log", env, session_id, window_id)
  end,
}

rex.action{
  name  = "spawn_cancel",
  title = "Close Spawn Picker",
  run   = function(ctx, args) close_picker(ctx) end,
}

rex.bind("cmd+ctrl+n", "spawn")
rex.bind("spawn/enter", "spawn_go")
rex.bind("spawn/escape", "spawn_cancel")
