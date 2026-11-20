-- cmd+shift+s: toggle a float running `scratch`, which opens a new
-- timestamped markdown file in nvim. Quitting nvim closes the float; pressing
-- the key again closes it too (unsaved edits are lost, so :w first).
--
-- The float opens on the focused session's host, and the scratch directory
-- lives in iCloud Drive, so it is only useful from a session on this Mac.
local util = require("switchyard.float")

local label = "scratch"
local bounds = { 0.1, 0.1, 0.8, 0.8 }

rex.action{
  name  = "scratch_float",
  title = "Toggle Scratch Note",
  run   = function(ctx, args)
    local layer = util.find_float(ctx, label)
    if layer ~= nil then
      local _, err = rex.session.close_layer{ session_id = ctx.session_id, layer_id = layer.layer_id }
      if err ~= nil then error(err, 0) end
      return
    end
    local _, err = rex.session.new_layer{
      session_id = ctx.session_id,
      bounds     = bounds,
      focus      = true,
      layout     = rex.layout.block{
        flavor  = "com.superlogical.terminal.shell",
        label   = label,
        options = { command = util.float_command("scratch") },
      },
    }
    if err ~= nil then error(err, 0) end
  end,
}

rex.bind("cmd+shift+s", "scratch_float")
