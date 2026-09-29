/**
 * Fernet Symmetric Cryptographic Engine
 *
 * Implements Fernet symmetric encryption and decryption compatible with
 * Python `cryptography.fernet` using native Node.js `crypto`.
 *
 * Fernet Spec:
 * - Key: 32 bytes (16 bytes signing key + 16 bytes encryption key), URL-safe base64 encoded.
 * - Token: Version (0x80, 1 byte) || Timestamp (8 bytes big-endian) || IV (16 bytes) || Ciphertext (AES-128-CBC PKCS7) || HMAC-SHA256 (32 bytes).
 * - Format: URL-safe base64 string.
 */

import * as crypto from "node:crypto";

const FERNET_VERSION = 0x80;
const MIN_TOKEN_LENGTH = 73; // 1 + 8 + 16 + 16 + 32

/**
 * Parses and validates a 32-byte URL-safe base64 encoded Fernet key.
 *
 * @param base64Key - The URL-safe base64 encoded 32-byte key string.
 * @returns Object containing signingKey (16 bytes) and encryptionKey (16 bytes).
 */
function parseFernetKey(base64Key: string): { signingKey: Buffer; encryptionKey: Buffer } {
  if (!base64Key || typeof base64Key !== "string" || !base64Key.trim()) {
    throw new Error("Fernet key must not be empty");
  }

  const trimmed = base64Key.trim();
  // Standardize URL-safe base64 to standard base64 and pad
  const padLen = (4 - (trimmed.length % 4)) % 4;
  const standardB64 =
    trimmed.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat(padLen);

  let keyBuf: Buffer;
  try {
    keyBuf = Buffer.from(standardB64, "base64");
  } catch (err) {
    throw new Error(
      `Invalid Fernet key encoding: ${err instanceof Error ? err.message : String(err)}`
    );
  }

  if (keyBuf.length !== 32) {
    throw new Error(
      `Fernet key must be 32 url-safe base64-encoded bytes, got ${keyBuf.length} bytes`
    );
  }

  return {
    signingKey: keyBuf.subarray(0, 16),
    encryptionKey: keyBuf.subarray(16, 32),
  };
}

/**
 * Generates a fresh URL-safe base64 encoded 32-byte Fernet key.
 * Compatible with `cryptography.fernet.Fernet.generate_key()`.
 *
 * @returns 44-character URL-safe base64 string ending with '=' padding.
 */
export function generateFernetKey(): string {
  const keyBytes = crypto.randomBytes(32);
  return keyBytes.toString("base64").replace(/\+/g, "-").replace(/\//g, "_");
}

/**
 * Encrypts session data into a Fernet token.
 *
 * @param data - Plaintext data string to encrypt.
 * @param base64Key - URL-safe base64 32-byte Fernet key.
 * @returns URL-safe base64 encoded Fernet token.
 */
export function encryptSession(data: string, base64Key: string): string {
  if (typeof data !== "string") {
    throw new Error("Data to encrypt must be a string");
  }

  const { signingKey, encryptionKey } = parseFernetKey(base64Key);

  // 1. Generate 16 random bytes for AES IV
  const iv = crypto.randomBytes(16);

  // 2. 64-bit big-endian timestamp in seconds
  const ts = BigInt(Math.floor(Date.now() / 1000));
  const tsBuf = Buffer.alloc(8);
  tsBuf.writeBigUInt64BE(ts, 0);

  // 3. Encrypt data with AES-128-CBC and PKCS7 padding
  const dataBuf = Buffer.from(data, "utf-8");
  const cipher = crypto.createCipheriv("aes-128-cbc", encryptionKey, iv);
  cipher.setAutoPadding(true);
  const ciphertext = Buffer.concat([cipher.update(dataBuf), cipher.final()]);

  // 4. Construct message for HMAC: Version || Timestamp || IV || Ciphertext
  const versionBuf = Buffer.from([FERNET_VERSION]);
  const basicParts = Buffer.concat([versionBuf, tsBuf, iv, ciphertext]);

  // 5. Compute HMAC-SHA256 using signingKey
  const hmac = crypto.createHmac("sha256", signingKey).update(basicParts).digest();

  // 6. Concatenate full token: basicParts || HMAC
  const tokenBuf = Buffer.concat([basicParts, hmac]);

  // 7. Return URL-safe base64 encoded string
  return tokenBuf.toString("base64").replace(/\+/g, "-").replace(/\//g, "_");
}

/**
 * Decrypts a Fernet token back into plaintext string.
 *
 * @param token - URL-safe base64 encoded Fernet token.
 * @param base64Key - URL-safe base64 32-byte Fernet key.
 * @returns Decrypted plaintext UTF-8 string.
 */
export function decryptSession(token: string, base64Key: string): string {
  if (!token || typeof token !== "string" || !token.trim()) {
    throw new Error("Fernet token must not be empty");
  }

  const { signingKey, encryptionKey } = parseFernetKey(base64Key);

  // 1. Decode token from URL-safe base64
  const trimmed = token.trim();
  const padLen = (4 - (trimmed.length % 4)) % 4;
  const standardB64 =
    trimmed.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat(padLen);

  let tokenBuf: Buffer;
  try {
    tokenBuf = Buffer.from(standardB64, "base64");
  } catch (err) {
    throw new Error(
      `Invalid Fernet token base64: ${err instanceof Error ? err.message : String(err)}`
    );
  }

  // 2. Validate token structure
  if (tokenBuf.length < MIN_TOKEN_LENGTH) {
    throw new Error(
      `Invalid Fernet token: length must be at least ${MIN_TOKEN_LENGTH} bytes, got ${tokenBuf.length}`
    );
  }

  // 3. Verify Version byte (0x80)
  if (tokenBuf[0] !== FERNET_VERSION) {
    throw new Error(
      `Invalid Fernet token version: expected 0x${FERNET_VERSION.toString(16)}, got 0x${tokenBuf[0].toString(16)}`
    );
  }

  // 4. Verify HMAC-SHA256 in constant time
  const basicParts = tokenBuf.subarray(0, tokenBuf.length - 32);
  const receivedHmac = tokenBuf.subarray(tokenBuf.length - 32);
  const computedHmac = crypto
    .createHmac("sha256", signingKey)
    .update(basicParts)
    .digest();

  if (
    receivedHmac.length !== computedHmac.length ||
    !crypto.timingSafeEqual(receivedHmac, computedHmac)
  ) {
    throw new Error("Invalid Fernet token: HMAC verification failed");
  }

  // 5. Extract IV (bytes 9..25) and Ciphertext (bytes 25..length-32)
  const iv = tokenBuf.subarray(9, 25);
  const ciphertext = tokenBuf.subarray(25, tokenBuf.length - 32);

  if (ciphertext.length % 16 !== 0) {
    throw new Error("Invalid Fernet token: ciphertext length is not a multiple of AES block size");
  }

  // 6. Decrypt ciphertext using AES-128-CBC
  try {
    const decipher = crypto.createDecipheriv("aes-128-cbc", encryptionKey, iv);
    decipher.setAutoPadding(true);
    const decrypted = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
    return decrypted.toString("utf-8");
  } catch (err) {
    throw new Error(
      `Fernet decryption failed: ${err instanceof Error ? err.message : String(err)}`
    );
  }
}
