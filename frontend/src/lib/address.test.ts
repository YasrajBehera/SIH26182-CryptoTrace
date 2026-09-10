import { describe, expect, it } from "vitest";
import {
  isLikelyAddress,
  isLikelyHash,
  validateAddressInput,
  containsSecretMaterial,
  normalizeAddressInput,
} from "@/lib/address";

describe("address utils", () => {
  it("accepts structurally-valid addresses", () => {
    expect(isLikelyAddress("0x1234567890abcdef1234567890abcdef12345678")).toBe(true);
    expect(validateAddressInput("0x1234567890abcdef1234567890abcdef12345678")).toBeNull();
  });

  it("rejects malformed addresses with safe guidance", () => {
    expect(validateAddressInput("")).toContain("Enter a wallet address");
    expect(validateAddressInput("0x123")).toContain("40 hexadecimal");
    expect(validateAddressInput("1234567890abcdef1234567890abcdef12345678")).toContain("must start with 0x");
    expect(isLikelyAddress("0xXYZ")).toBe(false);
  });

  it("detects 64-char transaction hashes", () => {
    expect(isLikelyHash(`0x${"a".repeat(64)}`)).toBe(true);
    expect(isLikelyHash("0x1234")).toBe(false);
  });

  it("never mistakes secret material for an address", () => {
    expect(containsSecretMaterial("my seed phrase is …")).toBe(true);
    expect(containsSecretMaterial("privateKey=0xdead…")).toBe(true);
    expect(containsSecretMaterial("export function main()")).toBe(false);
  });

  it("normalizes whitespace without mutating case", () => {
    expect(normalizeAddressInput("  0xAb12  ")).toBe("0xAb12");
  });
});