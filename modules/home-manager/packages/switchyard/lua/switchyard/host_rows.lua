-- One server's rows, run as `rex [-S HOST] do -e SCRIPT host=HOST`, or for
-- the config host `host=local`, which also shows its home as ~. The float
-- (tab-picker.lua) reads this file; rex-tab-picker builds it in for its
-- standalone mode. (`rex do` reads an argument value with a slash as a
-- script path and one like 6e6173 as a number, so the script looks up $HOME
-- and hex-encodes the label itself.)
local terminal = "com.superlogical.terminal"
local server, host = rex, rex.args.host
local home = host == "local" and rex.exec({ "sh", "-c", 'printf %s "$HOME"' }).stdout or ""
-- Hex keeps arbitrary host labels safe inside the terminal-title payload.
local target = host == "local" and "-" or host:gsub(".", function(c) return string.format("%02x", c:byte()) end)
local groups = {}
-- Agents report status per pane; a tab shows its most urgent one.
local urgency = { done = 1, working = 2, error = 3, blocked = 4 }
do
  local list, err = server.call("session.list")
  if list == nil then error(host .. ": " .. tostring(err), 0) end
  for _, session in ipairs(list.sessions or {}) do
    local _, attach_err = server.session.attach{ session_id = session.session_id }
    if attach_err ~= nil then error(attach_err, 0) end
    local view, view_err = server.session.view{ session_id = session.session_id }
    if view == nil then error(view_err, 0) end
    local tabs = {}
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
      local state
      for _, id in ipairs(blocks) do
        if id == window.focused_block_id then block_id = id end
        local status = server.block.call(terminal, "program_status",
          { session_id = session.session_id, block_id = id })
        for _, record in ipairs((status and status.records) or {}) do
          if (urgency[record.state] or 0) > (urgency[state] or 0) then
            state = record.state
          end
        end
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
        if home ~= "" and dir:sub(1, #home) == home then
          dir = "~" .. dir:sub(#home + 1)
        end
      end
      tabs[#tabs + 1] = { window_id = window.window_id, name = name, dir = dir, state = state }
    end
  end
end

-- rex-tab-picker draws the rows; see its source for the format.
local function clean(s) return (tostring(s or ""):gsub("[\t\r\n]", " ")) end
local lines = {}
for _, group in ipairs(groups) do
  local session = group.session
  lines[#lines + 1] = table.concat({
    "S", group.target, clean(group.host), session.session_id, clean(session.label or session.session_id),
  }, "\t")
  for _, tab in ipairs(group.tabs) do
    lines[#lines + 1] = table.concat({
      "T", tab.window_id, tab.state or "", clean(tab.name), clean(tab.dir),
    }, "\t")
  end
end
return table.concat(lines, "\n") .. "\n"
