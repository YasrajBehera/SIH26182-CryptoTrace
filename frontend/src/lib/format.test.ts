import { describe, expect, it } from "vitest";
import { shortenAddress, shortenHash, formatAmount, formatNumber, formatUsd, formatDate, chainLabel, fromNow } from "@/lib/format";

describe("format utils", () => {
  it("shortenAddress keeps short strings intact", () => {
    expect(shortenAddress("0xabcd")).toBe("0xabcd");
    expect(shortenAddress("")).toBe("");
    expect(shortenAddress(null)).toBe("");
  });

  it("shortenAddress truncates to head/tail with ellipsis", () => {
    const long = "0x1234567890abcdef1234567890abcdef12345678";
    expect(shortenAddress(long)).toBe("0x1234…5678");
    expect(shortenAddress(long, 8, 6)).toBe("0x123456…345678");
  });

  it("shortenHash delegates and truncates hashes", () => {
    const hash = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    expect(shortenHash(hash)).toContain("…");
    expect(shortenHash(hash).length).toBeLessThan(hash.length);
  });

  it("formatAmount handles null/empty and large magnitudes", () => {
    expect(formatAmount(null)).toBe("—");
    expect(formatAmount(undefined)).toBe("—");
    expect(formatAmount("")).toBe("—");
    expect(formatAmount(1234)).toBe("1.23K");
    expect(formatAmount(2_000_000)).toBe("2.00M");
    expect(formatAmount(1_500_000_000)).toBe("1.50B");
    expect(formatAmount(1234, "USDT")).toBe("1.23K USDT");
    expect(formatAmount(0.0001234)).toBe("0.000123");
  });

  it("formatNumber / formatUsd are deterministic", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatNumber(null)).toBe("—");
    expect(formatUsd(1234)).toBe("$1,234");
  });

  it("chainLabel maps known chains and falls back", () => {
    expect(chainLabel("eth")).toBe("Ethereum");
    expect(chainLabel("eth-mainnet")).toBe("Ethereum Mainnet");
    expect(chainLabel("polygon")).toBe("polygon");
    expect(chainLabel(null)).toBe("Unknown network");
  });

  it("formatDate/fromNow tolerate bad input", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("not-a-date")).toBe("not-a-date");
    expect(fromNow(null)).toBe("—");
    expect(fromNow(new Date())).toBe("just now");
  });
});