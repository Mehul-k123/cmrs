/**
 * Exact money helpers using integer paise, so the UI can preview differences (e.g. expected vs
 * received) without floating-point error. The server remains the source of truth for all totals.
 */
const MONEY_RE = /^\d+(\.\d{1,2})?$/;

export function isValidAmount(s: string): boolean {
  return MONEY_RE.test(s.trim());
}

export function toPaise(s: string): number {
  const [rupees, paise = ""] = s.trim().replace(/^-/, "").split(".");
  const value = Number(rupees) * 100 + Number(paise.padEnd(2, "0"));
  return s.trim().startsWith("-") ? -value : value;
}

export function fromPaise(p: number): string {
  const sign = p < 0 ? "-" : "";
  const abs = Math.abs(p);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

export function subtract(a: string, b: string): string {
  return fromPaise(toPaise(a) - toPaise(b));
}

export function sumMoney(values: string[]): string {
  return fromPaise(values.reduce((acc, v) => acc + toPaise(v), 0));
}

export function compare(a: string, b: string): number {
  return Math.sign(toPaise(a) - toPaise(b));
}
