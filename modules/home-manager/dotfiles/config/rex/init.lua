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
