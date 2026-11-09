-- Float helpers shared by the switchyard pickers and other Rex actions
-- (yem.lua in system-config requires them as "switchyard.float").
local M = {}

-- Find a floating layer by its block label in the action's session.
function M.find_float(ctx, label)
  local view = rex.session.view{ session_id = ctx.session_id }
  for _, window in ipairs((view and view.windows) or {}) do
    for _, layer in ipairs(window.layers or {}) do
      for _, block in ipairs(layer.blocks or {}) do
        if layer.kind ~= "tiled" and block.label == label then
          return layer, block.block_id
        end
      end
    end
  end
end

-- Close a picker float and leave its key mode.
function M.close_float(ctx, label)
  local layer = M.find_float(ctx, label)
  if layer ~= nil then
    rex.session.close_layer{ session_id = ctx.session_id, layer_id = layer.layer_id }
  end
  rex.client.queue("client.mode.exit_all")
end

-- The config host runs with a bare PATH, so find its rex CLI.
function M.user_path()
  local r = rex.exec({ "sh", "-c",
    'printf %s "$HOME/.local/bin:/etc/profiles/per-user/$(id -un)/bin:$PATH"' })
  return r.stdout
end

-- A float command that runs program from the user's PATH on the float's host.
function M.float_command(program, ...)
  return {
    "sh", "-c", 'PATH="$HOME/.local/bin:$HOME/.nix-profile/bin:/etc/profiles/per-user/$(id -un)/bin:$PATH"; export PATH; exec ' .. program .. ' "$@"',
    "sh", ...,
  }
end

-- Environment for rex CLI calls that must not inherit this server's targets.
function M.cli_env()
  return { PATH = M.user_path(), REX_SERVER = false, REX_CLIENT = false, REX_SESSION = false, REX_BLOCK = false }
end

-- The start of a `rex do` script that fills a float opened before its data
-- was ready. Run with session= and block= naming the float; the rest of the
-- script fetches and calls deliver(kind, body), which types
-- "rex-data:KIND\n" .. body into the float as a bracketed paste. Errors the
-- rest raises are delivered as kind "error". The float may be on any host,
-- so every server is asked for its session at once while the script fetches.
M.deliver_prelude = [==[
local T = "com.superlogical.terminal"
local float = { session_id = rex.args.session, block_id = rex.args.block }
local lookups = {}
for _, host in ipairs(rex.servers()) do
  lookups[#lookups + 1] = { host = host, job = rex.exec.start({ "rex", "-S", host, "do", "-e",
    -- `rex do` prints nothing for a boolean, so answer with a string.
    'local _, err = rex.session.attach{ session_id = rex.args.session } return err == nil and "found" or ""',
    "session=" .. float.session_id }) }
end
local server
local function float_server()
  if server ~= nil then return server end
  local _, err = rex.session.attach{ session_id = float.session_id }
  if err == nil then server = rex return server end
  for _, l in ipairs(lookups) do
    if (l.job:wait().stdout or ""):match("found") then
      server = rex.server(l.host)
      server.session.attach{ session_id = float.session_id }
      return server
    end
  end
  error("can't find the float's session " .. float.session_id, 0)
end
local function deliver(kind, body)
  local s = float_server()
  -- Wait (up to 5s) for the float program to take the terminal raw, so the
  -- paste isn't echoed or line-edited; give up if the float has closed.
  for _ = 1, 100 do
    local mode = s.block.call(T, "input_mode", float)
    if mode == nil then return end
    if not mode.canonical and not mode.echo then break end
    rex.sleep(0.05)
  end
  -- An escape in the body could end the paste early.
  local data = "\27[200~rex-data:" .. kind .. "\n" .. tostring(body):gsub("\27", "") .. "\27[201~"
  s.block.call(T, "write", { session_id = float.session_id, block_id = float.block_id, data = data })
end
local function main(fetch)
  local ok, err = pcall(fetch)
  if not ok then pcall(deliver, "error", tostring(err)) error(err, 0) end
end
]==]

-- Open a float running command at once and fill it in the background: a
-- detached `rex do` on this config host runs deliver_prelude .. script
-- against it, logging failures to log_name. Waiting in the action instead
-- would hold up the app's keys until the slowest host answered.
function M.open_filled_float(ctx, opts)
  local layer, layer_err = rex.session.new_layer{
    session_id = ctx.session_id,
    bounds     = opts.bounds,
    focus      = true,
    layout     = rex.layout.block{
      flavor  = "com.superlogical.terminal.shell",
      label   = opts.label,
      options = { command = opts.command },
    },
  }
  if layer == nil then error(layer_err, 0) end
  local block_id = (layer.block_ids or {})[1]
  if block_id == nil then error("new float has no block", 0) end
  rex.client.queue("client.mode.enter", { name = opts.mode })
  local job, err = rex.exec.start({
    "sh", "-c", 'umask 077; log="${XDG_STATE_HOME:-$HOME/.local/state}/rex/' .. opts.log_name .. '"; mkdir -p "${log%/*}" || exit; exec "$@" >> "$log" 2>&1',
    "sh", "rex", "do", "-e", M.deliver_prelude .. opts.script,
    "session=" .. ctx.session_id, "block=" .. block_id,
  }, { detach = true, env = M.cli_env() })
  if job == nil then error(err, 0) end
end

-- Pickers hex-encode values so they survive the terminal-title payload.
function M.unhex(s)
  return (s:gsub("%x%x", function(pair) return string.char(tonumber(pair, 16)) end))
end

-- Queued client actions belong to the config host, even with a remote
-- session focused. Select through the other host's app connection instead.
-- Detach so the app can finish the current action before handling the jump.
-- The CLI refuses ambiguous app targets; failures stay in log_name.
function M.select_on_host(host, log_name, env, session_id, window_id)
  local command = {
    "sh", "-c", 'umask 077; log="${XDG_STATE_HOME:-$HOME/.local/state}/rex/' .. log_name .. '"; mkdir -p "${log%/*}" || exit; exec "$@" >> "$log" 2>&1',
    "sh", "rex", "-S", host, "do", "session.select", "session_id=" .. session_id,
  }
  if window_id ~= nil then command[#command + 1] = "window_id=" .. window_id end
  local job, err = rex.exec.start(command, { detach = true, env = env })
  if job == nil then error(err, 0) end
end

return M
