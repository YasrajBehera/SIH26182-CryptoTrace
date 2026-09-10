/**
 * Client-side logging.
 *
 * SECURITY: never log secrets, auth tokens, wallet private keys or raw env
 * values. This logger surfaces concise, safe diagnostics only.
 */

type Level = "debug" | "info" | "warn" | "error";

const LEVEL_ORDER: Record<Level, number> = { debug: 10, info: 20, warn: 30, error: 40 };

function shouldLog(level: Level): boolean {
  const threshold = import.meta.env.DEV ? "debug" : "info";
  return LEVEL_ORDER[level] >= LEVEL_ORDER[threshold as Level];
}

function write(level: Level, message: string, data?: unknown): void {
  if (!shouldLog(level)) return;
  const prefix = `[CryptoTrace:${level}]`;
  if (level === "error") {
    console.error(prefix, message, data ?? "");
  } else if (level === "warn") {
    console.warn(prefix, message, data ?? "");
  } else if (level === "debug") {
    console.debug(prefix, message, data ?? "");
  } else {
    console.info(prefix, message, data ?? "");
  }
}

export const logger = {
  debug: (message: string, data?: unknown) => write("debug", message, data),
  info: (message: string, data?: unknown) => write("info", message, data),
  warn: (message: string, data?: unknown) => write("warn", message, data),
  error: (message: string, data?: unknown) => write("error", message, data),
};