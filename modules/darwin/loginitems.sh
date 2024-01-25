add_login_item() {
	local iname="$1"
	local ipath="/Applications/${iname}.app"

	osascript <<EOF
tell application "System Events"
    if not (exists login item "$iname") then
        make new login item at end with properties {name:"$iname", path:"$ipath", hidden:false}
    end if
end tell
EOF
}

apps=(
	# I _think_ AeroSpace is installing it's own LaunchAgent
	# AeroSpace
	"CleanShot X"
	Dropbox
	Lunar
	noTunes
	Ollama
	Rambox
	Raycast
	Rocket
)

for app in "${apps[@]}"; do
	add_login_item "$app"
done
