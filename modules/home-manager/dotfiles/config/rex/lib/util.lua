-- Helpers shared by the floating pickers.
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
