/**
 * Secret sealing. The web only ever ENCRYPTS — using the anonymous sealed-box
 * construction (crypto_box_seal) with a tenant's public key. Only the local
 * worker, which holds the matching private key, can decrypt (PyNaCl SealedBox).
 *
 * Wire format: base64(sealed_box(utf8(secret), tenantPublicKey)).
 * tweetnacl-sealedbox-js implements the same construction as libsodium's
 * crypto_box_seal, so it interops with PyNaCl's nacl.public.SealedBox.
 * Runs server-side only (Server Actions).
 */
import sealedbox from "tweetnacl-sealedbox-js";

/** Encrypt one secret string to a tenant's base64 public key. Returns base64 ciphertext. */
export async function sealSecret(plaintext: string, tenantPublicKeyB64: string): Promise<string> {
  const pk = new Uint8Array(Buffer.from(tenantPublicKeyB64, "base64"));
  const sealed = sealedbox.seal(new TextEncoder().encode(plaintext), pk);
  return Buffer.from(sealed).toString("base64");
}

/**
 * Field names we treat as secret per provider. The manage-keys UI seals these;
 * everything else is stored as non-secret `config`.
 */
export const SECRET_FIELDS: Record<string, string[]> = {
  apollo: ["APOLLO_API_KEY"],
  brevo: ["BREVO_API_KEY"],
  gemini: ["GEMINI_API_KEY"],
  erpnext: ["ERPNEXT_API_KEY", "ERPNEXT_API_SECRET"],
  whatsapp: ["OPENWA_API_KEY"],
  zoho: ["ZOHO_MCP_URL"], // the MCP URL embeds a token -> treat the whole URL as secret
};

/** Non-secret config fields per provider, shown/stored in clear. */
export const CONFIG_FIELDS: Record<string, string[]> = {
  apollo: ["APOLLO_BASE_URL"],
  brevo: ["BREVO_SENDER_NAME", "BREVO_SENDER_EMAIL"],
  gemini: ["GEMINI_MODEL"],
  erpnext: ["ERPNEXT_URL"],
  whatsapp: ["OPENWA_BASE_URL", "OPENWA_SESSION_ID", "WHATSAPP_DEFAULT_COUNTRY_CODE"],
  zoho: [],
};

/** Guard: assert a payload contains no known secret field (used before writing config/status). */
export function assertNoSecretLeak(payload: Record<string, unknown>) {
  const allSecrets = new Set(Object.values(SECRET_FIELDS).flat());
  for (const k of Object.keys(payload)) {
    if (allSecrets.has(k)) {
      throw new Error(`Refusing to store secret field '${k}' in a non-secret column.`);
    }
  }
}
