-- Mirror the Ghostty shortcuts plus the multiplexer chords Ghostty passes
-- through, since Rex owns sessions, tabs, and panes itself. Apply with
-- `rex config reload`.
--
-- Rex's require searches beside this file, so `config.keymaps` is
-- config/keymaps.lua and `switchyard` is switchyard/init.lua, which Home
-- Manager links from the switchyard package (its tab picker and new float).
-- Each action module binds its own keys.

require("config.keymaps")

require("switchyard")
require("actions.yem")
