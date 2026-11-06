-- Toggle a floating yem player. yem's TUI is a client of its daemon, so
-- closing the float leaves playback running.
--
-- yem only runs on this Mac, but a float opens on the focused session's host.
-- From a remote session, open the float in a local session instead and switch
-- to it, creating a "yem" session if there is none. The remote session is
-- remembered, so toggling the float closed jumps back to it.
local util = require("lib.util")

local label = "yem"
local shell = "com.superlogical.terminal.shell"
local bounds = { 0.05, 0.05, 0.9, 0.9 }

-- Quitting yem closes the float without running yem_float, so the float's
-- shell asks yem_return to finish the round trip when yem exits.
local float_command = {
  "sh", "-c", 'PATH="$HOME/.local/bin:/etc/profiles/per-user/$(id -un)/bin:$PATH"; export PATH; yem; '
    .. 'exec rex do yem_return session_id="$REX_SESSION" >/dev/null 2>&1',
}

local state_dir = (os.getenv("HOME") or "") .. "/.local/state/rex"
local state_path = state_dir .. "/yem-return"

-- The return trip: { local_session, host, session_id, window_id }.
local function read_state()
  local f = io.open(state_path, "r")
  if f == nil then return nil end
  local fields = {}
  for line in f:lines() do fields[#fields + 1] = line end
  f:close()
  if #fields < 3 then return nil end
  return {
    local_session = fields[1], host = fields[2], session_id = fields[3],
    window_id = (fields[4] ~= nil and fields[4] ~= "") and fields[4] or nil,
  }
end

local function write_state(s)
  rex.exec({ "mkdir", "-p", state_dir })
  local f, err = io.open(state_path, "w")
  if f == nil then error(err, 0) end
  f:write(table.concat({ s.local_session, s.host, s.session_id, s.window_id or "" }, "\n"), "\n")
  f:close()
end

local function clear_state() os.remove(state_path) end

-- Jump back to the remote session the float was opened from, if session_id
-- is the local session it hopped to.
local function return_from(session_id)
  local back = read_state()
  if back == nil or back.local_session ~= session_id then return end
  clear_state()
  util.select_on_host(back.host, "yem.log", util.cli_env(), back.session_id, back.window_id)
end

-- Server actions see only the focused session's server, so a `rex do` script
-- on this host finds which host owns the session. If it is remote, the script
-- picks a local session (the last hop's, then one labelled yem, then any,
-- else a new one) and opens the float there.
local hop_script = [==[
local target, preferred, command = %q, %q, { "sh", "-c", %q }
local label, shell = "yem", "com.superlogical.terminal.shell"
local bounds = { %s }

local function sessions(server)
  local list, err = server.call("session.list")
  if list == nil then error(err, 0) end
  return list.sessions or {}
end

local locals = sessions(rex)
for _, s in ipairs(locals) do
  if s.session_id == target then return { host = "local" } end
end

local owner
for _, host in ipairs(rex.servers()) do
  local ok, found = pcall(function()
    for _, s in ipairs(sessions(rex.server(host))) do
      if s.session_id == target then return true end
    end
  end)
  if ok and found then owner = host break end
end
if owner == nil then error("yem: no host owns session " .. target, 0) end

local pick
for _, s in ipairs(locals) do if s.session_id == preferred then pick = s.session_id end end
if pick == nil then
  for _, s in ipairs(locals) do if s.label == label then pick = s.session_id break end end
end
if pick == nil and locals[1] ~= nil then pick = locals[1].session_id end
if pick == nil then
  local created, err = rex.call("session.create", {
    label = label, initial_windows = { { layout = { block = { flavor = shell } } } },
  })
  if created == nil then error(err, 0) end
  pick = created.session_id
end

local _, attach_err = rex.session.attach{ session_id = pick }
if attach_err ~= nil then error(attach_err, 0) end
local view = rex.session.view{ session_id = pick }
for _, window in ipairs((view and view.windows) or {}) do
  for _, layer in ipairs(window.layers or {}) do
    for _, block in ipairs(layer.blocks or {}) do
      if layer.kind ~= "tiled" and block.label == label then
        return { host = owner, session_id = pick }
      end
    end
  end
end
local _, layer_err = rex.session.new_layer{
  session_id = pick, bounds = bounds, focus = true,
  layout = rex.layout.block{ flavor = shell, label = label, options = { command = command } },
}
if layer_err ~= nil then error(layer_err, 0) end
return { host = owner, session_id = pick }
]==]

rex.action{
  name  = "yem_float",
  title = "Toggle yem Player",
  run   = function(ctx, args)
    local back = read_state()

    local layer = util.find_float(ctx, label)
    if layer ~= nil then
      local _, close_err = rex.session.close_layer{ session_id = ctx.session_id, layer_id = layer.layer_id }
      if close_err ~= nil then error(close_err, 0) end
      return_from(ctx.session_id)
      return
    end

    -- A short timeout keeps an offline host from stalling the lookup.
    local script = string.format(hop_script, ctx.session_id,
      (back and back.local_session) or "", float_command[3], table.concat(bounds, ", "))
    local r, err = rex.exec({ "rex", "--timeout", "3s", "do", "-e", script }, { env = util.cli_env() })
    if r == nil then error(err, 0) end
    if not r.ok then error(r.stderr, 0) end
    local hop = rex.json.decode(r.stdout)

    if hop.host == "local" then
      -- Opened here directly, so closing it shouldn't jump anywhere.
      if back ~= nil and back.local_session == ctx.session_id then clear_state() end
      local _, new_err = rex.session.new_layer{
        session_id = ctx.session_id,
        bounds     = bounds,
        focus      = true,
        layout     = rex.layout.block{ flavor = shell, label = label, options = { command = float_command } },
      }
      if new_err ~= nil then error(new_err, 0) end
      return
    end

    -- Key actions carry no window_id, so remember the origin's active tab.
    local origin = rex.session.view{ session_id = ctx.session_id }
    write_state{
      local_session = hop.session_id, host = hop.host,
      session_id = ctx.session_id,
      window_id = ctx.window_id or (origin and origin.active_window_id),
    }
    rex.client.queue("session.select", { session_id = hop.session_id })
  end,
}
rex.action{
  name  = "yem_return",
  title = "Return From yem Player",
  args  = { session_id = "string" },
  run   = function(ctx, args) return_from(args.session_id) end,
}

rex.bind("cmd+shift+m", "yem_float")
