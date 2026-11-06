-- Mirror the Ghostty shortcuts plus the multiplexer chords Ghostty passes
-- through, since Rex owns sessions, tabs, and panes itself. Apply with
-- `rex config reload`.
--
-- Rex's require searches beside this file, so `config.keymaps` is
-- config/keymaps.lua. Each action module binds its own keys.

require("config.keymaps")

require("actions.project-picker")
require("actions.tab-picker")
require("actions.yem")
