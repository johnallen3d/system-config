-- Switchyard's Rex actions: `require("switchyard")` from a Rex init.lua
-- binds the cmd+k / cmd+i tab picker (tab-picker.lua) and the cmd+shift+n /
-- ctrl+cmd+n new float (new.lua). Install this directory as switchyard/
-- beside init.lua; Rex's require finds switchyard/init.lua and
-- switchyard/NAME.lua there. The float helpers (switchyard.float) are also
-- for other actions to require.
require("switchyard.new")
require("switchyard.tab-picker")
