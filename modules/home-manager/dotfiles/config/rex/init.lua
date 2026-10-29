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

-- Fuzzy-find any tab across sessions, like Herdr's project picker. A script
-- lists the tabs, fzf runs in a float, and its pick comes back through a FIFO
-- so the app can be asked to show that tab once `run` returns.
-- Config actions can only read their own session, so a `rex do` script, which
-- can attach to each one, lists the tabs.
local tab_list_script = [==[
local terminal = "com.superlogical.terminal"
local home = rex.exec({ "sh", "-c", 'printf %s "$HOME"' }).stdout
local list, err = rex.call("session.list")
if list == nil then error(err, 0) end
local lines = {}
for _, session in ipairs(list.sessions or {}) do
  local _, attach_err = rex.session.attach{ session_id = session.session_id }
  if attach_err ~= nil then error(attach_err, 0) end
  local view, view_err = rex.session.view{ session_id = session.session_id }
  if view == nil then error(view_err, 0) end
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
      local title = rex.block.call(terminal, "title", args)
      if name:match("^Window %x+$") and title and title.title ~= "" then
        name = title.title
      end
      local pwd = rex.block.call(terminal, "pwd", args)
      dir = ((pwd and pwd.pwd) or ""):gsub("^file://[^/]*", "")
      if home ~= "" and dir:sub(1, #home) == home then
        dir = "~" .. dir:sub(#home + 1)
      end
    end
    lines[#lines + 1] = table.concat({
      session.session_id, window.window_id,
      (session.label or "") .. "  " .. name .. "  " .. dir,
    }, "\t")
  end
end
return table.concat(lines, "\n") .. "\n"
]==]

-- The server runs with a bare PATH, so find rex and fzf where they're installed.
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

-- The picker's files live in one place so the actions below can find them.
local function picker_dir()
  return rex.exec({ "sh", "-c", 'printf %s "${TMPDIR:-/tmp}/rex-tab-picker-$(id -un)"' }).stdout
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
    local dir = picker_dir()
    local prep = rex.exec({ "sh", "-c", 'mkdir -p "$1" && rm -f "$1/pick" && cat > "$1/tabs"', "sh", dir },
      { stdin = entries })
    if not prep.ok then error(prep.stderr, 0) end

    local _, layer_err = rex.session.new_layer{
      session_id = ctx.session_id,
      bounds     = { 0.2, 0.15, 0.6, 0.6 },
      focus      = true,
      layout     = rex.layout.block{
        flavor  = "com.superlogical.terminal.shell",
        label   = "tab-picker",
        options = { command = {
          "sh", "-c", 'PATH=$1; export PATH; d=$2; shift 2; exec fzf "$@" < "$d/tabs"',
          "sh", path, dir,
          "--delimiter=\t", "--with-nth=3", "--reverse", "--prompt=tab> ",
          "--with-shell=sh -c",
          "--bind=focus:execute-silent(printf '%s\\t%s\\n' {1} {2} > " .. dir .. "/pick)",
          "--bind=zero:execute-silent(: > " .. dir .. "/pick)",
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
    local pick = rex.exec({ "cat", picker_dir() .. "/pick" })
    close_picker(ctx)
    local session_id, window_id = (pick.stdout or ""):match("^([^\t]+)\t([^\t\n]+)")
    if session_id ~= nil then
      rex.client.queue("session.select", { session_id = session_id, window_id = window_id })
    end
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
