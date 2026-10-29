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
