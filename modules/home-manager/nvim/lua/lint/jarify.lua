-- nvim-lint linter definition for jarify (https://github.com/amfaro/jarify)
-- Mirrors the structure of nvim-lint's built-in linter registry.

local severity_map = {
	error = vim.diagnostic.severity.ERROR,
	warn = vim.diagnostic.severity.WARN,
}

return {
	cmd = "jarify",
	stdin = true,
	args = {
		"lint",
		"--format",
		"json",
		"--stdin-filename",
		function()
			return vim.api.nvim_buf_get_name(0)
		end,
		"-",
	},
	ignore_exitcode = true,
	parser = function(output, bufnr)
		if output == nil or vim.trim(output) == "" then
			return {}
		end

		local ok, decoded = pcall(vim.json.decode, output)
		if not ok then
			return {}
		end

		local filename = vim.fs.normalize(vim.api.nvim_buf_get_name(bufnr))
		local diagnostics = {}

		for _, item in ipairs(decoded or {}) do
			local item_file = item.filename and vim.fs.normalize(item.filename) or filename
			if item_file == filename then
				local lnum = math.max((item.line or 1) - 1, 0)
				local col = math.max((item.column or 1) - 1, 0)
				table.insert(diagnostics, {
					lnum = lnum,
					col = col,
					end_lnum = lnum,
					end_col = col,
					message = string.format("[%s] %s", item.rule or "jarify", item.message),
					code = item.rule,
					source = "jarify",
					severity = severity_map[item.severity] or vim.diagnostic.severity.WARN,
				})
			end
		end

		return diagnostics
	end,
}
