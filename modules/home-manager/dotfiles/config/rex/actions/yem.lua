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
