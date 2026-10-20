/** Random idempotency key. crypto.randomUUID needs a secure context, so fall back to getRandomValues. */
export function uuid(): string {
  const c: Crypto = globalThis.crypto;
  if (typeof c.randomUUID === "function") return c.randomUUID();
  return Array.from(c.getRandomValues(new Uint8Array(16)), (x: number) => x.toString(16).padStart(2, "0")).join("");
}
