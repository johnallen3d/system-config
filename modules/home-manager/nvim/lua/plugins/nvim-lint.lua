vim.pack.add({ "https://github.com/mfussenegger/nvim-lint" }, { confirm = false })

local lint = require("lint")

lint.linters_by_ft = {
	markdown = { "markdownlint-cli2" },
	python = { "ruff" },
	sql = { "jarify" },
}

lint.linters.jarify = require("lint.jarify")

lint.linters["markdownlint-cli2"] = vim.tbl_deep_extend("force", require("lint.linters.markdownlint-cli2"), {
	args = {
		"--config",
		vim.fn.expand("~/.config/markdownlint/.markdownlint-cli2.jsonc"),
	},
})

vim.api.nvim_create_autocmd({ "BufReadPost", "BufEnter", "InsertLeave", "BufWritePost" }, {
	group = vim.api.nvim_create_augroup("NvimLint", { clear = true }),
	callback = function()
		vim.schedule(lint.try_lint)
	end,
})
