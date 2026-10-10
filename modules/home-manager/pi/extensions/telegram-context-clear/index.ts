import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { homedir } from "node:os";
import type ExtensionAPI from "@earendil-works/pi-coding-agent";

interface TelegramConfig {
	botToken?: string;
	allowedUserId?: number;
}

interface TelegramApiResponse<T> {
	ok: boolean;
	result?: T;
	description?: string;
}

const CONFIG_PATH = join(homedir(), ".pi", "agent", "telegram.json");
const CLEAR_COMMAND = "/clear-context";

function isPersonalProfile(): boolean {
	return !(process.env["PI_CODING_AGENT_DIR"] ?? "").endsWith("pi-work");
}

async function readJson<T>(path: string, fallback: T): Promise<T> {
	try {
		return JSON.parse(await readFile(path, "utf8")) as T;
	} catch {
		return fallback;
	}
}

async function telegram(config: TelegramConfig, text: string): Promise<void> {
	if (!config.botToken || !config.allowedUserId) return;
	const response = await fetch(`https://api.telegram.org/bot${config.botToken}/sendMessage`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify({ chat_id: config.allowedUserId, text }),
	});
	const data = (await response.json()) as TelegramApiResponse<unknown>;
	if (!data.ok) throw new Error(data.description || "Telegram sendMessage failed");
}

// Manual Telegram clearing only; context usage must not trigger unsolicited alerts.
export default function (pi: ExtensionAPI) {
	pi.on("input", async (event, ctx) => {
		if (!isPersonalProfile() || event.source !== "extension") return { action: "continue" };
		if (event.text.trim() !== `[telegram] ${CLEAR_COMMAND}`) return { action: "continue" };

		await ctx.newSession();
		const config = await readJson<TelegramConfig>(CONFIG_PATH, {});
		await telegram(config, "Pi session cleared.");
		return { action: "handled" };
	});
}
