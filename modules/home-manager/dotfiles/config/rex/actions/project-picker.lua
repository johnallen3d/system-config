-- Pick a zoxide folder with rex-project-picker and switch to the session named
-- after it, creating one if needed. It lists the focused host's folders; Tab
-- moves to another Rex host. The float runs on the focused session's host,
-- which may have no route back here, so this host passes in its own label,
-- folders, and hosts, and finishes the pick itself as the tab picker does.
local util = require("lib.util")

local label = "project-session"

local function close_picker(ctx) util.close_float(ctx, label) end

local function host_label()
  return (rex.exec({ "hostname", "-s" }).stdout:gsub("%s+$", ""))
end

rex.mode("project_picker")

rex.action{
  name  = "project_session",
  title = "New Session in Directory…",
  run   = function(ctx, args)
    if util.find_float(ctx, label) ~= nil then return close_picker(ctx) end
    local folders = rex.exec({ "zoxide", "query", "-l" }, { env = { PATH = util.user_path() } })
    local command = util.float_command("rex-project-picker",
      host_label(), (folders and folders.ok and folders.stdout) or "")
    -- rex.servers() is empty inside a server action; ask the CLI, as the tab
    -- picker does.
    local hosts = rex.exec({ "rex", "do", "-e", 'return table.concat(rex.servers(), "\\n")' },
      { env = util.cli_env() })
    if hosts and hosts.ok then
      for host in rex.json.decode(hosts.stdout):gmatch("[^\n]+") do command[#command + 1] = host end
    end
    local _, err = rex.session.new_layer{
      session_id = ctx.session_id,
      bounds     = { 0.12, 0.1, 0.76, 0.75 },
      focus      = true,
      layout     = rex.layout.block{
        flavor  = "com.superlogical.terminal.shell",
        label   = label,
        options = { command = command },
      },
    }
    if err ~= nil then error(err, 0) end
    rex.client.queue("client.mode.enter", { name = "project_picker" })
  end,
}

rex.action{
  name  = "project_session_go",
  title = "Open Picked Directory",
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
    local host, dir = ((pick and pick.title) or ""):match("^rex%-project%-picker:(%x+)/(%x+)$")
    if host == nil then return end
    close_picker(ctx)
    host, dir = util.unhex(host), util.unhex(dir)
    local env = util.cli_env()
    local r, err = rex.exec({ "rex-project-picker", "--open", host, dir }, { env = env })
    if r == nil then error(err, 0) end
    if not r.ok or r.stdout == "" then error(r.stderr, 0) end
    if host == host_label() then
      rex.client.queue("session.select", { session_id = r.stdout })
      return
    end
    util.select_on_host(host, "project-picker.log", env, r.stdout)
  end,
}

rex.action{
  name  = "project_session_cancel",
  title = "Close Project Picker",
  run   = function(ctx, args) close_picker(ctx) end,
}

rex.bind("cmd+shift+n", "project_session")
rex.bind("project_picker/enter", "project_session_go")
rex.bind("project_picker/escape", "project_session_cancel")
