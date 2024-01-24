#!/usr/bin/env lua

-- Add the sketchybar module to the package cpath (the module could be
-- installed into the default search path then this would not be needed)
package.cpath = package.cpath
	.. ";/Users/"
	.. os.getenv("USER")
	.. "/.local/share/sketchybar_lua/?.so"

package.path = package.path .. ";../sketchybar/?.lua"

-- Require the sketchybar module
Sbar = require("sketchybar")

-- Specify which bar
Sbar.set_bar_name("bottombar")

-- Load the init.lua file
require("init")

Sbar.hotload(true)

-- Load helper scripts
os.execute("pgrep mpd-updater | xargs kill -9")
os.execute(os.getenv("HOME") .. "/.config/bottombar/plugins/mpd-updater &")

-- Run the event loop of the sketchybar module (without this there will be no
-- bi-directional communication between the lua module and sketchybar)
Sbar.event_loop()
