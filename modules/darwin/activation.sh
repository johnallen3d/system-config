#
# add desired applications to Login Items
#
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

#
# TODO: this works however  runs every time and will open/close a Finder window
# each time. 🤮 So far I'm unable to test if the desired favorite already
# exists. presumably the file here has this information but I haven't het
# figured out how to read it.
#
# ~/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.FavoriteItems.sfl2
#
# add home to Finder Favorites
#
# osascript <<'END_SCRIPT'
# tell application "Finder"
#     set homeFolder to home
#     open homeFolder
#     activate
# end tell

# tell application "System Events"
#     delay 1
#     tell process "Finder"
#         keystroke "t" using {command down, control down}
#     end tell
# end tell

# tell application "Finder"
#     -- Close the frontmost Finder window (should be the new one)
#     try
#       close Finder window 1
#     on error
#         -- If an error occurs, continue without notifying
#     end try
# end tell
# END_SCRIPT
