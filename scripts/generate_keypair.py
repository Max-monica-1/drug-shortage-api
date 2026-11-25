"""Generate an RSA key pair for Snowflake key-pair authentication."""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Store keys in a local folder that is ignored by Git
keys_dir = Path("keys")
keys_dir.mkdir(exist_ok=True)

# Generate a 2048-bit RSA private key
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# Save the private key (PKCS#8 format, required by Snowflake)
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
(keys_dir / "rsa_key.p8").write_bytes(private_pem)

# Save the public key
public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)
(keys_dir / "rsa_key.pub").write_bytes(public_pem)

# Print the public key body (without header/footer lines) for Snowflake
body = "".join(
    line for line in public_pem.decode().splitlines() if "-----" not in line
)
print("Public key for Snowflake:")
print(body)