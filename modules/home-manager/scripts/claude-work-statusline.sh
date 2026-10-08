# Resolve only this profile's registered user plugin, not an arbitrary cached version.
profile="${CLAUDE_CONFIG_DIR:-$HOME/.config/claude-gmatter}"
manifest="$profile/plugins/installed_plugins.json"
[ -f "$manifest" ] || exit 0
plugin_dir="$(jq -r '.plugins["agent-kit@amfaro"] // [] | map(select(.scope == "user")) | first | .installPath // empty' "$manifest")"
[ -n "$plugin_dir" ] && [ -f "$plugin_dir/claude-code/statusline.mjs" ] || exit 0
exec node "$plugin_dir/claude-code/statusline.mjs"
