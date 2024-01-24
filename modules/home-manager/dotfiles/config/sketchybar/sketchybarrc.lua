#!/usr/bin/env lua

-- This is only needed once to install the sketchybar module
-- (or for an update of the module)
-- os.execute("(git clone https://github.com/FelixKratz/SbarLua.git /tmp/SbarLua && cd /tmp/SbarLua/ && make install && rm -rf /tmp/SbarLua/)")

-- Add the sketchybar module to the package cpath (the module could be
-- installed into the default search path then this would not be needed)
package.cpath = package.cpath
	.. ";/Users/"
	.. os.getenv("USER")
	.. "/.local/share/sketchybar_lua/sketchybar.so"

-- Require the sketchybar module
-- TODO: why does the process hang at this point?
Sbar = require("sketchybar")

-- Specify which bar (only necessary if not default: sketchybar)
Sbar.set_bar_name("sketchybar")

-- Load the init.lua file
require("init")

Sbar.hotload(true)

-- Load helper scripts
os.execute("killall weather-updater")
os.execute(os.getenv("HOME") .. "/.config/sketchybar/plugins/weather-updater &")

-- Run the event loop of the sketchybar module (without this there will be no
-- bi-directional communication between the lua module and sketchybar)
Sbar.event_loop()

-- #!/usr/bin/env bash
--
-- sketchybar --bar color=0xff000000
-- sketchybar --add item test left --set test label="Click Me" click_script='osascript -e "display dialog \"Works\""'
