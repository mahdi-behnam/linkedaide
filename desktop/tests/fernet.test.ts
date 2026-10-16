import { describe, expect, it } from "vitest";
import { execSync } from "node:child_process";
import {
  decryptSession,
  encryptSession,
  generateFernetKey,
} from "../electron/crypto/fernet";

describe("Fernet Cryptography Engine", () => {
  describe("generateFernetKey", () => {
    it("generates a valid 44-character url-safe base64 key ending with '='", () => {
      const key = generateFernetKey();
      expect(typeof key).toBe("string");
      expect(key.length).toBe(44);
      expect(key.endsWith("=")).toBe(true);

      const standardB64 = key.replace(/-/g, "+").replace(/_/g, "/");
      const buf = Buffer.from(standardB64, "base64");
      expect(buf.length).toBe(32);
    });

    it("generates unique keys across multiple invocations", () => {
      const key1 = generateFernetKey();
      const key2 = generateFernetKey();
      expect(key1).not.toBe(key2);
    });
  });

  describe("Round-trip Encryption & Decryption", () => {
    it("successfully encrypts and decrypts a simple message", () => {
      const key = generateFernetKey();
      const message = "Hello from LinkedAide Desktop!";
      const token = encryptSession(message, key);

      expect(typeof token).toBe("string");
      expect(token).not.toBe(message);

      const decrypted = decryptSession(token, key);
      expect(decrypted).toBe(message);
    });

    it("handles empty string correctly", () => {
      const key = generateFernetKey();
      const message = "";
      const token = encryptSession(message, key);
      const decrypted = decryptSession(token, key);
      expect(decrypted).toBe(message);
    });

    it("handles multi-byte UTF-8 characters and emojis", () => {
      const key = generateFernetKey();
      const message = "🚀 LinkedAide • 自动化测试 • 🔒 Encryption verified";
      const token = encryptSession(message, key);
      const decrypted = decryptSession(token, key);
      expect(decrypted).toBe(message);
    });

    it("handles complex JSON storage_state payloads", () => {
      const key = generateFernetKey();
      const mockStorageState = JSON.stringify({
        cookies: [
          {
            name: "li_at",
            value: "AQEDASampleCookieValueXYZ1234567890",
            domain: ".linkedin.com",
            path: "/",
            expires: 1790000000,
            httpOnly: true,
            secure: true,
            sameSite: "None",
          },
        ],
        origins: [
          {
            origin: "https://www.linkedin.com",
            localStorage: [{ name: "voyager-web:feed", value: "cached-data" }],
          },
        ],
      });

      const token = encryptSession(mockStorageState, key);
      const decrypted = decryptSession(token, key);
      expect(decrypted).toBe(mockStorageState);
      expect(JSON.parse(decrypted)).toEqual(JSON.parse(mockStorageState));
    });
  });

  describe("Invalid Key Detection", () => {
    it("throws error when key is empty or whitespace", () => {
      expect(() => encryptSession("data", "")).toThrow("Fernet key must not be empty");
      expect(() => decryptSession("token", "   ")).toThrow("Fernet key must not be empty");
    });

    it("throws error when key is not 32 bytes", () => {
      // 16-byte base64
      const shortKey = Buffer.alloc(16).toString("base64");
      expect(() => encryptSession("data", shortKey)).toThrow(
        /Fernet key must be 32 url-safe base64-encoded bytes/
      );

      // 48-byte base64
      const longKey = Buffer.alloc(48).toString("base64");
      expect(() => encryptSession("data", longKey)).toThrow(
        /Fernet key must be 32 url-safe base64-encoded bytes/
      );
    });

    it("throws HMAC verification error when decrypting with different key", () => {
      const key1 = generateFernetKey();
      const key2 = generateFernetKey();
      const token = encryptSession("secret payload", key1);

      expect(() => decryptSession(token, key2)).toThrow(
        /HMAC verification failed/
      );
    });
  });

  describe("Invalid Token Rejection", () => {
    const key = generateFernetKey();

    it("throws error on empty token", () => {
      expect(() => decryptSession("", key)).toThrow("Fernet token must not be empty");
      expect(() => decryptSession("   ", key)).toThrow("Fernet token must not be empty");
    });

    it("throws error on truncated token (< 73 bytes)", () => {
      const tooShort = Buffer.alloc(50).toString("base64url");
      expect(() => decryptSession(tooShort, key)).toThrow(
        /length must be at least 73 bytes/
      );
    });

    it("throws error on invalid version byte", () => {
      const validToken = encryptSession("test message", key);
      const standardB64 = validToken.replace(/-/g, "+").replace(/_/g, "/");
      const tokenBuf = Buffer.from(standardB64, "base64");

      // Corrupt version byte (0x80 -> 0x81)
      tokenBuf[0] = 0x81;
      const corrupted = tokenBuf.toString("base64url");

      expect(() => decryptSession(corrupted, key)).toThrow(/Invalid Fernet token version/);
    });

    it("throws error on tampered HMAC", () => {
      const validToken = encryptSession("test message", key);
      const standardB64 = validToken.replace(/-/g, "+").replace(/_/g, "/");
      const tokenBuf = Buffer.from(standardB64, "base64");

      // Flip a bit in the last byte (HMAC)
      tokenBuf[tokenBuf.length - 1] ^= 0x01;
      const corrupted = tokenBuf.toString("base64url");

      expect(() => decryptSession(corrupted, key)).toThrow(/HMAC verification failed/);
    });

    it("throws error on tampered ciphertext", () => {
      const validToken = encryptSession("test message", key);
      const standardB64 = validToken.replace(/-/g, "+").replace(/_/g, "/");
      const tokenBuf = Buffer.from(standardB64, "base64");

      // Flip a bit in the ciphertext section (offset 26)
      tokenBuf[26] ^= 0x01;
      const corrupted = tokenBuf.toString("base64url");

      expect(() => decryptSession(corrupted, key)).toThrow(/HMAC verification failed/);
    });

    it("throws error on tampered timestamp", () => {
      const validToken = encryptSession("test message", key);
      const standardB64 = validToken.replace(/-/g, "+").replace(/_/g, "/");
      const tokenBuf = Buffer.from(standardB64, "base64");

      // Flip a bit in timestamp (bytes 1..8)
      tokenBuf[5] ^= 0x01;
      const corrupted = tokenBuf.toString("base64url");

      expect(() => decryptSession(corrupted, key)).toThrow(/HMAC verification failed/);
    });
  });

  describe("Python cryptography.fernet Cross-Compatibility", () => {
    it("decrypts a token generated by Python", () => {
      const key = generateFernetKey();
      const pythonScript = `
import base64
from cryptography.fernet import Fernet
f = Fernet("${key}")
token = f.encrypt(b"Hello from Python cryptography.fernet!")
print(token.decode("utf-8"))
`;
      const pythonToken = execSync("python3", {
        input: pythonScript,
        encoding: "utf-8",
      }).trim();

      const decryptedInNode = decryptSession(pythonToken, key);
      expect(decryptedInNode).toBe("Hello from Python cryptography.fernet!");
    });

    it("generates a token that Python can decrypt", () => {
      const key = generateFernetKey();
      const payload = "Hello from Node.js Fernet engine!";
      const nodeToken = encryptSession(payload, key);

      const pythonScript = `
from cryptography.fernet import Fernet
f = Fernet("${key}")
plaintext = f.decrypt(b"${nodeToken}")
print(plaintext.decode("utf-8"))
`;
      const pythonDecrypted = execSync("python3", {
        input: pythonScript,
        encoding: "utf-8",
      }).trim();

      expect(pythonDecrypted).toBe(payload);
    });
  });
});
