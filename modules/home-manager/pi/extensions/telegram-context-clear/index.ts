import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
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

interface State {
	askedAt?: number;
	lastPercent?: number;
}

const CONFIG_PATH = join(homedir(), ".pi", "agent", "telegram.json");
const STATE_PATH = join(homedir(), ".local", "state", "pi", "telegram-context-clear.json");
const THRESHOLD_PERCENT = Number(process.env["PI_TELEGRAM_CONTEXT_CLEAR_THRESHOLD"] ?? "70");
const MIN_ASK_INTERVAL_MS = 30 * 60 * 1000;
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

async function writeState(state: State): Promise<void> {
	await mkdir(dirname(STATE_PATH), { recursive: true });
	await writeFile(STATE_PATH, `${JSON.stringify(state, null, "\t")}\n`, "utf8");
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

export default function (pi: ExtensionAPI) {
	pi.on("input", async (event, ctx) => {
		if (!isPersonalProfile() || event.source !== "extension") return { action: "continue" };
		if (event.text.trim() !== `[telegram] ${CLEAR_COMMAND}`) return { action: "continue" };

		await ctx.newSession();
		const config = await readJson<TelegramConfig>(CONFIG_PATH, {});
		await telegram(config, "Pi session cleared.");
		await writeState({});
		return { action: "handled" };
	});

	pi.on("agent_end", async (_event, ctx) => {
		if (!isPersonalProfile()) return;
		const percent = ctx.getContextUsage().percent ?? 0;
		if (percent < THRESHOLD_PERCENT) return;

		const state = await readJson<State>(STATE_PATH, {});
		if (state.askedAt && Date.now() - state.askedAt < MIN_ASK_INTERVAL_MS) return;

		const config = await readJson<TelegramConfig>(CONFIG_PATH, {});
		await telegram(config, `Pi context is ${percent.toFixed(1)}% full. Reply ${CLEAR_COMMAND} to clear active session.`);
		await writeState({ askedAt: Date.now(), lastPercent: percent });
	});
}
