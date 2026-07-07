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

interface TelegramUpdate {
	update_id: number;
	callback_query?: {
		id: string;
		data?: string;
		from: { id: number };
		message?: { chat: { id: number } };
	};
}

interface State {
	nonce?: string;
	askedAt?: number;
	lastPercent?: number;
	lastUpdateId?: number;
}

const CONFIG_PATH = join(homedir(), ".pi", "agent", "telegram.json");
const STATE_PATH = join(homedir(), ".local", "state", "pi", "telegram-context-clear.json");
const THRESHOLD_PERCENT = Number(process.env["PI_TELEGRAM_CONTEXT_CLEAR_THRESHOLD"] ?? "70");
const MIN_ASK_INTERVAL_MS = 30 * 60 * 1000;
const POLL_MS = 5000;
const COMMAND = "/telegram-context-clear-confirm";

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

async function telegram<T>(config: TelegramConfig, method: string, body: Record<string, unknown>): Promise<T | undefined> {
	if (!config.botToken) return undefined;
	const response = await fetch(`https://api.telegram.org/bot${config.botToken}/${method}`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify(body),
	});
	const data = (await response.json()) as TelegramApiResponse<T>;
	if (!data.ok) throw new Error(data.description || `Telegram API ${method} failed`);
	return data.result;
}

async function sendClearPrompt(config: TelegramConfig, percent: number, nonce: string): Promise<void> {
	if (!config.allowedUserId) return;
	await telegram(config, "sendMessage", {
		chat_id: config.allowedUserId,
		text: `Pi context is ${percent.toFixed(1)}% full. Clear active session instead of compacting?`,
		reply_markup: {
			inline_keyboard: [[
				{ text: "Clear context", callback_data: `pi-clear:${nonce}` },
				{ text: "Keep session", callback_data: `pi-keep:${nonce}` },
			]],
		},
	});
}

export default function (pi: ExtensionAPI) {
	let pollTimer: ReturnType<typeof setInterval> | undefined;
	let clearWhenIdle = false;

	async function requestClear(): Promise<void> {
		clearWhenIdle = true;
		await pi.sendUserMessage(COMMAND);
	}

	pi.registerCommand("telegram-context-clear-confirm", {
		description: "Clear active session after Telegram confirmation",
		handler: async (_args, ctx) => {
			if (!ctx.isIdle()) {
				clearWhenIdle = true;
				return;
			}
			clearWhenIdle = false;
			await ctx.newSession();
			const config = await readJson<TelegramConfig>(CONFIG_PATH, {});
			if (config.allowedUserId) {
				await telegram(config, "sendMessage", {
					chat_id: config.allowedUserId,
					text: "Pi session cleared.",
				});
			}
		},
	});

	async function pollCallbacks(): Promise<void> {
		const config = await readJson<TelegramConfig>(CONFIG_PATH, {});
		if (!config.botToken || !config.allowedUserId) return;
		const state = await readJson<State>(STATE_PATH, {});
		const updates = await telegram<TelegramUpdate[]>(config, "getUpdates", {
			offset: state.lastUpdateId === undefined ? undefined : state.lastUpdateId + 1,
			limit: 10,
			timeout: 0,
			allowed_updates: ["callback_query"],
		});
		if (!updates?.length) return;

		let nextState = state;
		for (const update of updates) {
			nextState = { ...nextState, lastUpdateId: update.update_id };
			const callback = update.callback_query;
			if (!callback || callback.from.id !== config.allowedUserId || !nextState.nonce) continue;
			if (callback.data === `pi-clear:${nextState.nonce}`) {
				await telegram(config, "answerCallbackQuery", { callback_query_id: callback.id, text: "Clearing context" });
				nextState = { lastUpdateId: update.update_id };
				await writeState(nextState);
				await requestClear();
			} else if (callback.data === `pi-keep:${nextState.nonce}`) {
				await telegram(config, "answerCallbackQuery", { callback_query_id: callback.id, text: "Keeping session" });
				nextState = { lastUpdateId: update.update_id };
			}
		}
		await writeState(nextState);
	}

	pi.on("session_start", async (_event, ctx) => {
		if (!isPersonalProfile()) return;
		if (!pollTimer) {
			pollTimer = setInterval(() => void pollCallbacks().catch((error) => ctx.ui.notify(String(error), "warning")), POLL_MS);
		}
	});

	pi.on("agent_end", async (_event, ctx) => {
		if (!isPersonalProfile()) return;
		if (clearWhenIdle && ctx.isIdle()) {
			await requestClear();
			return;
		}

		const usage = ctx.getContextUsage();
		const percent = usage.percent ?? 0;
		if (percent < THRESHOLD_PERCENT) return;

		const state = await readJson<State>(STATE_PATH, {});
		if (state.nonce || (state.askedAt && Date.now() - state.askedAt < MIN_ASK_INTERVAL_MS)) return;

		const config = await readJson<TelegramConfig>(CONFIG_PATH, {});
		const nonce = Math.random().toString(36).slice(2, 10);
		await sendClearPrompt(config, percent, nonce);
		await writeState({ ...state, nonce, askedAt: Date.now(), lastPercent: percent });
	});

	pi.on("session_shutdown", async () => {
		if (pollTimer) clearInterval(pollTimer);
		pollTimer = undefined;
	});
}
