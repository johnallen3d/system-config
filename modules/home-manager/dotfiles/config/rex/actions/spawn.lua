-- Spawn agent work with rex-spawn: a catalog project, a work name and an
-- optional first prompt for the agent; the host defaults to the project's pool (see rex-spawn's `pool`) and the harness to Claude. The
-- picker runs in a float on the focused session's host and reports its
-- choice in the terminal title (a prompt as a reference to a file on the
-- picker's host, which --launch collects); Enter launches from this
-- config host, the only one that can reach every Rex host. The new tab runs
-- `rex-spawn --run` on the target host, which makes the worktree with wt and
-- starts the agent there. See packages/switchyard/crates/spawn/src/main.rs.
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
    local session_id = ctx.session_id
    if session_id == nil then
      -- With no session to float over, make one with a shell and switch to it.
      local created, create_err = rex.call("session.create", {
        initial_windows = { { layout = { block = { flavor = "com.superlogical.terminal.shell" } } } },
      })
      if created == nil then error(create_err, 0) end
      session_id = created.session_id
      rex.client.queue("session.select", { session_id = session_id })
    elseif util.find_float(ctx, label) ~= nil then
      return close_picker(ctx)
    end
    local _, err = rex.session.new_layer{
      session_id = session_id,
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
    local title = (pick and pick.title) or ""
    local host, path, name, harness = title:match("^rex%-spawn:(%x+)/(%x+)/(%x+)/(%a+)$")
    local prompt_ref
    if host == nil then
      host, path, name, harness, prompt_ref = title:match("^rex%-spawn:(%x+)/(%x+)/(%x+)/(%a+)/(%x+)$")
    end
    -- An incomplete form reports nothing; keep the float open.
    if host == nil then return end
    close_picker(ctx)
    host = util.unhex(host)
    local env = util.cli_env()
    local argv = { "rex-spawn", "--launch", host, util.unhex(path), util.unhex(name), harness }
    if prompt_ref ~= nil then table.insert(argv, util.unhex(prompt_ref)) end
    local r, err = rex.exec(argv, { env = env })
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
-- Escape is left to the picker, which asks before discarding a prompt.
