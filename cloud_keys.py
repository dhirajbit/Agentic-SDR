"""Per-tenant keypair management for the sealed-box secret channel.

The worker generates one libsodium box keypair per tenant on first use, stores
the PRIVATE key locally (tenants/<slug>/.worker_key, chmod 600, gitignored), and
publishes the PUBLIC key so the web can encrypt secrets to it. Only this worker
can decrypt — the web/DB never see plaintext.
"""

import base64
import os
from pathlib import Path

from nacl.public import PrivateKey, SealedBox

REPO_ROOT = Path(__file__).resolve().parent


def _key_path(slug: str) -> Path:
    return REPO_ROOT / "tenants" / slug / ".worker_key"


def ensure_keypair(slug: str) -> str:
    """Return the tenant's base64 public key, generating + persisting the private
    key on first call. Private key file is created with 0600 perms."""
    path = _key_path(slug)
    if path.exists():
        priv = PrivateKey(base64.b64decode(path.read_text().strip()))
    else:
        priv = PrivateKey.generate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(base64.b64encode(bytes(priv)).decode())
        os.chmod(path, 0o600)
    return base64.b64encode(bytes(priv.public_key)).decode()


def load_private(slug: str) -> PrivateKey:
    path = _key_path(slug)
    if not path.exists():
        raise FileNotFoundError(
            f"No worker key for {slug}. Run the agent once to generate it ({path})."
        )
    return PrivateKey(base64.b64decode(path.read_text().strip()))


def decrypt_secret(slug: str, ciphertext_b64: str) -> str:
    """Decrypt one sealed-box ciphertext (base64) produced by the web's seal.ts."""
    box = SealedBox(load_private(slug))
    return box.decrypt(base64.b64decode(ciphertext_b64)).decode()
