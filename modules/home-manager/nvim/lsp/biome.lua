return {
  cmd = function(_, config)
    local root_dir = config and config.root_dir or nil
    local local_cmd = root_dir and (root_dir .. "/node_modules/.bin/biome")
      or nil
    local cmd = (local_cmd and vim.fn.executable(local_cmd) == 1) and local_cmd
      or "biome"
    return vim.lsp.rpc.start({ cmd, "lsp-proxy" })
  end,
  filetypes = {
    "astro",
    "css",
    "graphql",
    "html",
    "javascript",
    "javascriptreact",
    "json",
    "jsonc",
    "svelte",
    "typescript",
    "typescript.tsx",
    "typescriptreact",
    "vue",
  },
  root_dir = function(bufnr)
    local root_markers = {
      "package-lock.json",
      "yarn.lock",
      "pnpm-lock.yaml",
      "bun.lockb",
      "bun.lock",
    }
    local project_root = vim.fs.root(bufnr, root_markers)
    if not project_root then
      return nil
    end

    -- Look for biome config in the project tree
    local biome_config_files = { "biome.json", "biome.jsonc" }
    local filename = vim.api.nvim_buf_get_name(bufnr)
    local found = vim.fs.find(biome_config_files, {
      path = filename,
      type = "file",
      upward = true,
      stop = vim.fs.dirname(project_root),
      limit = 1,
    })[1]
    if found then
      return project_root
    end
    return nil
  end,
}
