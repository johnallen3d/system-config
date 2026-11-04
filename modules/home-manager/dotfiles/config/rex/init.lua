-- Mirror the Ghostty shortcuts plus the Herdr chords Ghostty passes through,
-- since Rex owns sessions, tabs, and panes itself. Herdr workspaces map to
-- Rex sessions. Apply with `rex config reload`.
--
-- Rex's require searches beside this file, so `config.keymaps` is
-- config/keymaps.lua. Each action module binds its own keys.

require("config.keymaps")

require("actions.project-picker")
require("actions.tab-picker")
require("actions.yem")
