-- 'unnamedplus' disables Neovim's automatic OSC 52 fallback. SSH sessions
-- without a display must opt in explicitly to reach the client clipboard.
-- Leave native desktop providers and explicit user/GUI providers alone.
local function present(value)
  return value ~= nil and value ~= ""
end

if
  present(vim.env.SSH_CONNECTION)
  and not present(vim.env.WAYLAND_DISPLAY)
  and not present(vim.env.DISPLAY)
  and vim.g.clipboard == nil
then
  vim.g.clipboard = "osc52"
end
