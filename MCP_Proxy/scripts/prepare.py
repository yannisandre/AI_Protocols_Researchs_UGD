"""Generate development-only keys and certificates; never install a CA system-wide."""
import ipaddress
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".") / ".local"
if (root / "ready").exists():
    print("Existing laboratory secrets retained.")
    raise SystemExit(0)
root.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc)
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MCP proxy research lab CA")])
ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
      .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5))
      .not_valid_after(now+timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
      .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
      .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False)
      .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                     data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
                     encipher_only=None, decipher_only=None), True)
      .sign(ca_key, hashes.SHA256()))
(root / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
for service in ("proxy", "mcp-server", "collector"):
    folder = root / (service + "-tls")
    folder.mkdir(mode=0o700)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, service)]))
            .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=90))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(service), x509.DNSName("localhost"),
                            x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=True,
                           data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
                           encipher_only=None, decipher_only=None), True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .sign(ca_key, hashes.SHA256()))
    (folder / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keypath = folder / "key.pem"
    keypath.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    keypath.chmod(0o600)
    (folder / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
values = {k: secrets.token_urlsafe(32) for k in ("host_control", "server_token", "collector_write", "collector_read")}
for service, names in {"agent": ["host_control"], "proxy": ["host_control", "server_token", "collector_read"],
                       "mcp-server": ["server_token", "collector_write"],
                       "collector": ["collector_write", "collector_read"]}.items():
    folder = root / (service + "-secrets")
    folder.mkdir(mode=0o700)
    for token in names:
        path = folder / token
        path.write_text(values[token] + "\n"); path.chmod(0o600)
for service in ("proxy", "mcp-server", "collector"):
    (root / (service + "-data")).mkdir(mode=0o700)
(root / "ready").write_text("Development certificates expire after 90 days. Regenerate only while the lab is stopped.\n")
print("Created per-service laboratory certificates and tokens. No system trust store was modified.")
