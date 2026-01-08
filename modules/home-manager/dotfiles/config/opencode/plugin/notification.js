export const NotificationPlugin = async ({ client, $ }) => {
	return {
		event: async ({ event }) => {
			// Send notification on session completion
			if (event.type === "session.idle") {
				await $`osascript -e 'display notification "Response completed!" with title "opencode"'`;
				await $`afplay /System/Library/Sounds/Funk.aiff`;
			}

			// Send notification when agent needs permission
			if (event.type === "permission.asked") {
				await $`osascript -e 'display notification "Permission requested" with title "opencode"'`;
				await $`afplay /System/Library/Sounds/Funk.aiff`;
			}
		},
	};
};
