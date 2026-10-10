-- Invoked by tests/omarchy-nvim.py against both installed editor profiles.
local profile = vim.env.NVIM_TEST_PROFILE
assert(vim.fn.has("nvim-0.12") == 1 and vim.pack, "Neovim 0.12+ is required")
assert(vim.g.mapleader == ",", "leader differs from Mac")
assert(vim.g.colors_name == require("theme.managed").colorscheme, "managed theme not loaded")
assert(vim.o.clipboard == "unnamedplus", "clipboard differs from Mac")
assert(vim.go.shiftwidth == 2 and vim.go.expandtab, "global indentation differs from Mac")
assert(package.loaded["blink.cmp"] and package.loaded["snacks"], "completion/picker not loaded")

if profile == "nvim" then
	for _, name in ipairs({
		"conform",
		"lint",
		"nvim-treesitter",
		"ufo",
		"oil",
		"flash",
		"grug-far",
		"noice",
	}) do
		assert(package.loaded[name], "plugin not loaded: " .. name)
	end
	for _, key in ipairs({ ",ff", ",sg", ",lf" }) do
		assert(vim.fn.maparg(key, "n") ~= "", "missing mapping: " .. key)
	end
	assert(vim.lsp.is_enabled("harper-ls"), "Harper LSP not enabled")
	assert(vim.o.undofile and not vim.o.swapfile, "editing options differ from Mac")
	-- Exercise a real parser, formatter, linter, and LSP, not only module loading.
	vim.cmd.edit(vim.env.NVIM_TEST_FILE)
	local parser = vim.treesitter.get_parser(0, "markdown")
	assert(#parser:parse() > 0, "Markdown parser did not parse")
	local format_error
	require("conform").format({ async = false, timeout_ms = 20000 }, function(err)
		format_error = err
	end)
	assert(not format_error, tostring(format_error))
	assert(vim.api.nvim_buf_get_lines(0, 0, 1, false)[1] == "# Editor smoke test")
	assert(
		vim.wait(20000, function()
			return #vim.lsp.get_clients({ bufnr = 0, name = "harper-ls" }) > 0
		end),
		"Harper did not attach"
	)
	for _, key in ipairs({ ",rn", ",ca", "gd", "gr" }) do
		assert(vim.fn.maparg(key, "n") ~= "", "missing LSP mapping: " .. key)
	end
	require("lint").try_lint()
	assert(
		vim.wait(20000, function()
			return #require("lint").get_running() == 0
		end),
		"Markdown linter did not finish"
	)
	for _, diagnostic in ipairs(vim.diagnostic.get(0)) do
		assert(not diagnostic.message:find("JSONParseError"), diagnostic.message)
	end
else
	assert(profile == "nvim-editor")
	assert(package.loaded["pibuf"] and package.loaded["markdown-plus"], "editor plugins not loaded")
	assert(vim.fn.maparg("<C-A>", "n") ~= "", "select-all mapping missing")
	vim.cmd.edit(vim.env.NVIM_TEST_FILE)
	assert(vim.bo.filetype == "pi", "Pi external-editor buffer not detected")
	assert(vim.wo.spell and vim.wo.wrap, "Pi buffer options not configured")
	assert(vim.fn.filereadable(vim.fn.stdpath("config") .. "/words") == 1, "dictionary missing")
end
print("PASS " .. profile .. " startup, plugins, theme, keybindings, and editing behavior")
