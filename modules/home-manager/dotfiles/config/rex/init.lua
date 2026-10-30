-- Mirror the Ghostty shortcuts plus the Herdr chords Ghostty passes through,
-- since Rex owns sessions, tabs, and panes itself. Herdr workspaces map to
-- Rex sessions. Apply with `rex config reload`.

-- Ghostty
rex.bind("cmd+n", "client.window.new")
rex.bind("cmd+shift+r", "client.config.reload")
rex.bind("cmd+f", "client.find.open")
rex.bind("cmd+q", "pane.close")
rex.bind("cmd+=", "client.font.increase")
rex.bind("cmd+-", "client.font.decrease")
rex.bind("cmd+0", "client.font.reset")
rex.bind("cmd+ctrl+=", "pane.balance")

-- Herdr workspaces
rex.bind("cmd+ctrl+n", "session.new")
rex.bind("cmd+s", "client.sidebar.toggle")

-- Herdr tabs and panes
rex.bind("cmd+t", "client.tab.new")
rex.bind("ctrl+tab", "client.tab.next")
rex.bind("ctrl+shift+tab", "client.tab.previous")
rex.bind("cmd+w", "pane.close")
rex.bind("cmd+d", "pane.split.right")
rex.bind("cmd+shift+d", "pane.split.down")

local directions = { h = "left", j = "down", k = "up", l = "right" }
for key, direction in pairs(directions) do
  rex.bind("cmd+ctrl+" .. key, "pane.focus." .. direction)
  rex.bind("cmd+ctrl+alt+" .. key, "pane.resize", { direction = direction })
end

-- Toggle a floating yem player. yem's TUI is a client of its daemon, so
-- closing the float leaves playback running.
rex.action{
  name  = "yem_float",
  title = "Toggle yem Player",
  run   = function(ctx, args)
    local view, err = rex.session.view{}
    if err ~= nil then error(err, 0) end
    for _, window in ipairs(view.windows or {}) do
      for _, layer in ipairs(window.layers or {}) do
        for _, block in ipairs(layer.blocks or {}) do
          if layer.kind ~= "tiled" and block.label == "yem" then
            local _, close_err = rex.session.close_layer{ layer_id = layer.layer_id }
            if close_err ~= nil then error(close_err, 0) end
            return
          end
        end
      end
    end
    local _, new_err = rex.session.new_layer{
      bounds = { 0.05, 0.05, 0.9, 0.9 },
      focus  = true,
      layout = rex.layout.block{
        flavor  = "com.superlogical.terminal.shell",
        label   = "yem",
        options = { command = { "yem" } },
      },
    }
    if new_err ~= nil then error(new_err, 0) end
  end,
}
rex.bind("cmd+shift+m", "yem_float")

-- Fuzzy-find tabs across sessions and hosts, like Herdr's project picker.
-- A `rex do` script can attach to every session on each configured server.
-- Pass its rows directly to the float: rex.exec runs on the config host,
-- while the float runs on the focused session's host. fzf records its pick
-- in the terminal title, which the action can read through the session API.
-- Each session gets a header row that picks its current tab.
local tab_list_script = [==[
local terminal = "com.superlogical.terminal"
local home = rex.exec({ "sh", "-c", 'printf %s "$HOME"' }).stdout
local groups = {}
local function collect(server, host)
  local list, err = server.call("session.list")
  if list == nil then error(host .. ": " .. tostring(err), 0) end
  for _, session in ipairs(list.sessions or {}) do
    local _, attach_err = server.session.attach{ session_id = session.session_id }
    if attach_err ~= nil then error(attach_err, 0) end
    local view, view_err = server.session.view{ session_id = session.session_id }
    if view == nil then error(view_err, 0) end
    local tabs = {}
    -- Hex keeps arbitrary host labels safe inside the terminal-title payload.
    local target = server == rex and "-" or host:gsub(".", function(c)
      return string.format("%02x", c:byte())
    end)
    groups[#groups + 1] = { session = session, tabs = tabs, host = host, target = target }
    for _, window in ipairs(view.windows or {}) do
      local blocks = {}
      for _, layer in ipairs(window.layers or {}) do
        if layer.kind == "tiled" then
          for _, block in ipairs(layer.blocks or {}) do
            blocks[#blocks + 1] = block.block_id
          end
        end
      end
      local block_id = blocks[1]
      for _, id in ipairs(blocks) do
        if id == window.focused_block_id then block_id = id end
      end
      local args = { session_id = session.session_id, block_id = block_id }
      local name = window.label or ""
      local dir = ""
      if block_id ~= nil then
        local title = server.block.call(terminal, "title", args)
        if name:match("^Window %x+$") and title and title.title ~= "" then
          name = title.title
        end
        local pwd = server.block.call(terminal, "pwd", args)
        dir = ((pwd and pwd.pwd) or ""):gsub("^file://[^/]*", "")
        if host == "local" and home ~= "" and dir:sub(1, #home) == home then
          dir = "~" .. dir:sub(#home + 1)
        end
      end
      tabs[#tabs + 1] = { window_id = window.window_id, name = name, dir = dir }
    end
  end
end
collect(rex, "local")
for _, host in ipairs(rex.servers()) do
  collect(rex.server(host), host)
end

local function width(s) return (utf8 and utf8.len(s)) or #s end
local max_name = 48
local name_width = 0
for _, group in ipairs(groups) do
  for _, tab in ipairs(group.tabs) do
    if width(tab.name) > max_name then
      local cut = (utf8 and utf8.offset(tab.name, max_name)) or max_name
      tab.name = tab.name:sub(1, cut - 1) .. "…"
    end
    name_width = math.max(name_width, width(tab.name))
  end
end

local lines = {}
for _, group in ipairs(groups) do
  local session = group.session
  lines[#lines + 1] = table.concat({
    session.session_id, "", group.target,
    "\27[1;35m[" .. group.host .. "] " .. (session.label or session.session_id) .. "\27[0m",
  }, "\t")
  for _, tab in ipairs(group.tabs) do
    lines[#lines + 1] = table.concat({
      session.session_id, tab.window_id, group.target,
      "  " .. tab.name .. string.rep(" ", name_width - width(tab.name))
        .. "  \27[2m" .. tab.dir .. "\27[0m",
    }, "\t")
  end
end
return table.concat(lines, "\n") .. "\n"
]==]

-- The config host runs with a bare PATH, so find its rex CLI.
local function user_path()
  local r = rex.exec({ "sh", "-c",
    'printf %s "$HOME/.local/bin:/etc/profiles/per-user/$(id -un)/bin:$PATH"' })
  return r.stdout
end

local function tab_entries(path)
  local r, err = rex.exec({ "rex", "do", "-e", tab_list_script }, { env = { PATH = path } })
  if r == nil then error(err, 0) end
  if not r.ok then error(r.stderr, 0) end
  return rex.json.decode(r.stdout)
end

local function picker_layer(ctx)
  local view = rex.session.view{ session_id = ctx.session_id }
  for _, window in ipairs((view and view.windows) or {}) do
    for _, layer in ipairs(window.layers or {}) do
      for _, block in ipairs(layer.blocks or {}) do
        if layer.kind ~= "tiled" and block.label == "tab-picker" then
          return layer, block.block_id
        end
      end
    end
  end
end

local function close_picker(ctx)
  local layer = picker_layer(ctx)
  if layer ~= nil then
    rex.session.close_layer{ session_id = ctx.session_id, layer_id = layer.layer_id }
  end
  rex.client.queue("client.mode.exit_all")
end

-- An action that waits for fzf holds up the app's keys, so this one opens the
-- float and returns. fzf records the highlighted tab as it moves, and the
-- tab_picker mode turns Enter and Escape into the actions that finish.
rex.mode("tab_picker")

rex.action{
  name  = "tab_picker",
  title = "Go to Tab…",
  run   = function(ctx, args)
    if picker_layer(ctx) ~= nil then return close_picker(ctx) end
    local path = user_path()
    local entries = tab_entries(path)
    local _, layer_err = rex.session.new_layer{
      session_id = ctx.session_id,
      bounds     = { 0.12, 0.1, 0.76, 0.75 },
      focus      = true,
      layout     = rex.layout.block{
        flavor  = "com.superlogical.terminal.shell",
        label   = "tab-picker",
        options = { command = {
          "sh", "-c", 'PATH="$HOME/.local/bin:$HOME/.nix-profile/bin:/etc/profiles/per-user/$(id -un)/bin:$PATH"; export PATH; entries=$1; shift; printf %s "$entries" | fzf "$@"',
          "sh", entries,
          "--delimiter=\t", "--with-nth=4", "--ansi", "--no-sort", "--reverse",
          "--prompt=tab> ",
          "--with-shell=sh -c",
          "--bind=focus:execute-silent(printf '\\033]2;rex-tab-picker:%s/%s/%s\\007' {3} {1} {2} > /dev/tty)",
          "--bind=zero:execute-silent(printf '\\033]2;rex-tab-picker:\\007' > /dev/tty)",
        } },
      },
    }
    if layer_err ~= nil then error(layer_err, 0) end
    rex.client.queue("client.mode.enter", { name = "tab_picker" })
  end,
}

rex.action{
  name  = "tab_picker_go",
  title = "Go to Picked Tab",
  run   = function(ctx, args)
    local _, block_id = picker_layer(ctx)
    if block_id == nil or block_id ~= ctx.block_id then
      close_picker(ctx)
      rex.client.queue("pane.send_key", { key = "enter" })
      return
    end
    local pick = rex.block.call("com.superlogical.terminal", "title", {
      session_id = ctx.session_id, block_id = block_id,
    })
    close_picker(ctx)
    local host, session_id, window_id = ((pick and pick.title) or ""):match("^rex%-tab%-picker:([^/]+)/([^/]+)/([^/]*)$")
    if session_id == nil then return end
    if host == "-" then
      rex.client.queue("session.select", {
        session_id = session_id, window_id = window_id ~= "" and window_id or nil,
      })
      return
    end
    host = host:gsub("%x%x", function(pair) return string.char(tonumber(pair, 16)) end)
    -- Queued client actions belong to the config host, even with a remote
    -- session focused. Use the selected host's app connection instead.
    -- Detach so the app can finish this action before handling the jump.
    -- The CLI refuses ambiguous app targets; failures stay in this log.
    local command = {
      "sh", "-c", 'umask 077; log="${XDG_STATE_HOME:-$HOME/.local/state}/rex/tab-picker.log"; mkdir -p "${log%/*}" || exit; exec "$@" >> "$log" 2>&1',
      "sh", "rex", "-S", host, "do", "session.select", "session_id=" .. session_id,
    }
    if window_id ~= "" then command[#command + 1] = "window_id=" .. window_id end
    local job, err = rex.exec.start(command, {
      detach = true,
      env = { PATH = user_path(), REX_SERVER = false, REX_CLIENT = false, REX_SESSION = false, REX_BLOCK = false },
    })
    if job == nil then error(err, 0) end
  end,
}

rex.action{
  name  = "tab_picker_cancel",
  title = "Close Tab Picker",
  run   = function(ctx, args) close_picker(ctx) end,
}

rex.bind("cmd+k", "tab_picker")
rex.bind("tab_picker/enter", "tab_picker_go")
rex.bind("tab_picker/escape", "tab_picker_cancel")
