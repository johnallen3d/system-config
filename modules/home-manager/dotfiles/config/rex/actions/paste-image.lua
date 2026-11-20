-- Cmd+V that carries clipboard images to remote panes.
--
-- A paste event only carries text, and a program on another host (Claude
-- Code, say) reads that host's clipboard, not the Mac's. So when the focused
-- pane belongs to a remote host and the clipboard holds an image (or a copied
-- image file), copy it to the host over SSH and paste its path, the way a
-- dropped file arrives. Anything else is an ordinary paste.
--
-- The action runs on the Mac (rex.exec, the clipboard), while rex.call goes
-- to the focused session's server, which names its host in server.status.

-- Hosts reachable over SSH, by the label in their Rex Tailscale name.
local ssh_targets = {
  omarchy = "johna@omarchy",
  miller  = "johna@miller",
  drummer = "johna@drummer",
}

-- Prints "file" and the path when the clipboard holds a copied image file,
-- such as a screenshot tool's (which also carries the image itself), or
-- "image" after writing a bare clipboard image to argv[1] as a PNG. Text or
-- another kind of file is left to the normal paste.
local clip_script = {
  "on run argv",
  "set kinds to (clipboard info) as text",
  'if kinds contains "furl" then',
  "set p to POSIX path of (the clipboard as «class furl»)",
  'set lower to do shell script "printf %s " & quoted form of p & " | tr A-Z a-z"',
  'repeat with ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}',
  'if lower ends with ext then return "file" & linefeed & p',
  "end repeat",
  'return "text"',
  "end if",
  'if kinds contains "utf8" or kinds contains "ut16" then return "text"',
  "try",
  "set img to the clipboard as «class PNGf»",
  "on error",
  'return "none"',
  "end try",
  "set f to open for access (POSIX file (item 1 of argv)) with write permission",
  "set eof f to 0",
  "write img to f",
  "close access f",
  'return "image"',
  "end run",
}

math.randomseed(os.time())

local function remote_target()
  local status = rex.call("server.status")
  local dns = status and status.tailscale and status.tailscale.dns_name
  local label = dns and dns:match("^rex%-([%w%-]+)%.")
  return label and ssh_targets[label]
end

-- Returns the remote path of the uploaded image, or nil when the clipboard
-- holds no image, or nil and an error.
local function upload(target)
  local tmp = rex.exec({ "/usr/bin/mktemp", "-t", "rex-paste" })
  if tmp == nil or not tmp.ok then return nil, "mktemp failed" end
  local file = (tmp.stdout:gsub("%s+$", ""))

  local argv = { "/usr/bin/osascript" }
  for _, line in ipairs(clip_script) do
    argv[#argv + 1] = "-e"
    argv[#argv + 1] = line
  end
  argv[#argv + 1] = file
  local clip, err = rex.exec(argv, { timeout = 5 })
  if clip == nil or not clip.ok then
    os.remove(file)
    return nil, clip == nil and err or clip.stderr
  end

  local ext = "png"
  local kind, path = clip.stdout:match("^(%a+)\n?(.-)%s*$")
  if kind == "file" then
    -- Into the mode 600 temp file, so the remote copy is private too.
    ext = path:match("%.(%w+)$"):lower()
    local cp = rex.exec({ "/bin/cp", path, file })
    if cp == nil or not cp.ok then
      os.remove(file)
      return nil, cp and cp.stderr or "cp failed"
    end
  elseif kind ~= "image" then
    os.remove(file)
    return nil
  end

  local remote = string.format("/tmp/rex-paste-%s-%06d.%s",
    os.date("%Y%m%d-%H%M%S"), math.random(0, 999999), ext)
  -- The file is mode 600, so scp creates the remote copy private too.
  local copy, copy_err = rex.exec({
    "/usr/bin/scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
    file, target .. ":" .. remote,
  }, { timeout = 20 })
  os.remove(file)
  if copy == nil then return nil, copy_err end
  if not copy.ok then return nil, copy.stderr end
  return remote
end

rex.action{
  name     = "paste_image",
  title    = "Paste, Sending Images to Remote Panes",
  category = "Pane",
  run      = function(ctx, args)
    local target = ctx.session_id and ctx.block_id and remote_target()
    if target ~= nil then
      local path, err = upload(target)
      if path ~= nil then
        local _, paste_err = rex.call("block.event", {
          session_id = ctx.session_id,
          block_id = ctx.block_id,
          event = { type = "paste", payload = { text = path } },
        })
        if paste_err == nil then return end
        err = paste_err
      end
      if err ~= nil then rex.log("warn", "paste_image: " .. tostring(err)) end
    end
    rex.client.queue("pane.paste")
  end,
}

rex.bind("cmd+v", "paste_image")

