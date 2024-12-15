return {
	{
		"stevearc/conform.nvim",
		opts = {
			formatters_by_ft = {
				kcl = { "kcl" },
				nix = { "alejandra" },
			},
			formatters = {
				kcl = {
					command = "/Users/john.allen/bin/kcl",
				},
				-- 	-- https://github.com/stevearc/conform.nvim/issues/204#issuecomment-1819517054
				-- 	csharpier = {
				-- 		args = { "--write-stdout", "--no-cache", "$FILENAME" },
				-- 	},
			},
		},
	},
}
