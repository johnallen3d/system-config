-- New sessions and agent work in one float, rex-spawn's picker: cmd+shift+n
-- opens it as a plain session, ctrl+cmd+n as agent work (ctrl-s switches).
-- It lists the catalog's projects and the zoxide folders of one host (ctrl-o
-- picks the host; `auto` runs agent work on the least busy dev host, and a
-- session on the focused host). The float runs on the focused session's host
-- and reports its pick in the terminal title, hex encoded:
--   rex-new:session/HOST/PATH
--   rex-new:agent/HOST/PATH/NAME/HARNESS[/PROMPT_REF]
-- Enter acts from this config host, the only one that can reach every Rex
-- host: a session opens with `rex-spawn --open`, and agent work launches
-- with `rex-spawn --launch`, which opens a tab running `--run` on the target
-- host (the worktree and the harness are made there). See
-- packages/switchyard/crates/spawn/src/main.rs.
local util = require("lib.util")

local label = "new-picker"
-- Labels the shell of a session made only to hold the picker, so a pick can
-- close it again.
local host_shell = "new-host"

local function close_picker(ctx) util.close_float(ctx, label) end

local function host_label()
  return (rex.exec({ "hostname", "-s" }).stdout:gsub("%s+$", ""))
end

-- True when the session is one this action made to float over: a single
-- tab holding only its labelled shell.
local function holds_only_picker_shell(ctx)
  local view = rex.session.view{ session_id = ctx.session_id }
  local windows = (view and view.windows) or {}
  if #windows ~= 1 then return false end
  local found = false
  for _, layer in ipairs(windows[1].layers or {}) do
    if layer.kind == "tiled" then
      local blocks = layer.blocks or {}
      if #blocks ~= 1 or blocks[1].label ~= host_shell then return false end
      found = true
    end
  end
  return found
end

-- Show the pick's tab or session on its host, then drop the picker's own
-- session when it only held the picker.
local function show(ctx, host, session_id, window_id)
  local env = util.cli_env()
  if host == host_label() then
    rex.client.queue("session.select", { session_id = session_id, window_id = window_id })
  else
    util.select_on_host(host, "new-picker.log", env, session_id, window_id)
  end
  if session_id ~= ctx.session_id and holds_only_picker_shell(ctx) then
    local _, destroy_err = rex.call("session.destroy", { session_id = ctx.session_id })
    if destroy_err ~= nil then error(destroy_err, 0) end
  end
end

rex.mode("new")

-- Open the picker in a float over the focused session, starting as `kind`
-- ("session" or "agent"). The float's folders are this host's; the config
-- host's are passed in as the --home folders.
local function open_picker(ctx, kind)
  local session_id = ctx.session_id
  if session_id == nil then
    -- With no session to float over, make one with a shell and switch to it.
    local created, create_err = rex.call("session.create", {
      initial_windows = { { layout = rex.layout.block{
        flavor = "com.superlogical.terminal.shell", label = host_shell,
      } } },
    })
    if created == nil then error(create_err, 0) end
    session_id = created.session_id
    rex.client.queue("session.select", { session_id = session_id })
  elseif util.find_float(ctx, label) ~= nil then
    return close_picker(ctx)
  end
  local folders = rex.exec({ "zoxide", "query", "-l" }, { env = { PATH = util.user_path() } })
  local command = util.float_command("rex-spawn", "--kind", kind, "--home", host_label(),
    (folders and folders.ok and folders.stdout) or "")
  local _, err = rex.session.new_layer{
    session_id = session_id,
    bounds     = { 0.12, 0.08, 0.76, 0.8 },
    focus      = true,
    layout     = rex.layout.block{
      flavor  = "com.superlogical.terminal.shell",
      label   = label,
      options = { command = command },
    },
  }
  if err ~= nil then error(err, 0) end
  rex.client.queue("client.mode.enter", { name = "new" })
end

rex.action{
  name  = "new_session",
  title = "New Session in Directory…",
  run   = function(ctx, args) open_picker(ctx, "session") end,
}

rex.action{
  name  = "new_agent",
  title = "Spawn Agent Work…",
  run   = function(ctx, args) open_picker(ctx, "agent") end,
}

rex.action{
  name  = "new_go",
  title = "Open Picked Session or Agent Work",
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
    local kind, rest = title:match("^rex%-new:(%a+)/(.*)$")
    local env = util.cli_env()

    if kind == "session" then
      local host, dir = rest:match("^(%x+)/(%x+)$")
      -- An incomplete pick reports nothing; keep the float open.
      if host == nil then return end
      close_picker(ctx)
      host, dir = util.unhex(host), util.unhex(dir)
      local r, err = rex.exec({ "rex-spawn", "--open", host, dir }, { env = env })
      if r == nil then error(err, 0) end
      if not r.ok or r.stdout == "" then error(r.stderr, 0) end
      show(ctx, host, r.stdout)
      return
    end

    if kind == "agent" then
      local host, path, name, harness = rest:match("^(%x+)/(%x+)/(%x+)/(%a+)$")
      local prompt_ref
      if host == nil then
        host, path, name, harness, prompt_ref = rest:match("^(%x+)/(%x+)/(%x+)/(%a+)/(%x+)$")
      end
      -- An incomplete form reports nothing; keep the float open.
      if host == nil then return end
      close_picker(ctx)
      local argv = { "rex-spawn", "--launch", util.unhex(host), util.unhex(path), util.unhex(name), harness }
      if prompt_ref ~= nil then table.insert(argv, util.unhex(prompt_ref)) end
      local r, err = rex.exec(argv, { env = env })
      if r == nil then error(err, 0) end
      if not r.ok then error(r.stderr, 0) end
      -- With host "auto", --launch picks the host and reports it first.
      local session_id, window_id
      host, session_id, window_id = r.stdout:match("^(%S+)\t(%S+)\t(%S+)$")
      if session_id == nil then error("rex-spawn: unexpected launch output: " .. r.stdout, 0) end
      show(ctx, host, session_id, window_id)
    end
  end,
}

rex.bind("cmd+shift+n", "new_session")
rex.bind("cmd+ctrl+n", "new_agent")
rex.bind("new/enter", "new_go")
