export const NotificationPlugin = async ({ client, $ }) => {
	return {
		event: async ({ event }) => {
			// Send notification on session completion
			if (event.type === "session.idle") {
				await $`osascript -e 'display notification "Response completed!" with title "opencode"'`;
				await $`afplay ~/bin/opencode-bell.wav`;
			}
		},
	};
};
