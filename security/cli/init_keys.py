"""
CLI Command to Initialize Orbitron Contact Issuer Keys
Usage:
    python -m security.cli.init_keys --output-dir security/.runtime/issuer [--force]
"""

import argparse
import sys
from pathlib import Path
from security.tokens.keys import init_issuer_keys


def main():
    parser = argparse.ArgumentParser(description="Initialize Ed25519 issuer keys for Orbitron contact tokens")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="security/.runtime/issuer",
        help="Directory to save private.pem and public.pem",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing key files if present",
    )

    args = parser.parse_args()

    try:
        priv_path, pub_path = init_issuer_keys(output_dir=args.output_dir, overwrite=args.force)
        print(f"[SUCCESS] Initialized Ed25519 issuer keys in: {Path(args.output_dir).resolve()}")
        print(f"  Private key: {priv_path}")
        print(f"  Public key:  {pub_path}")
        sys.exit(0)
    except FileExistsError as e:
        print(f"[INFO] {e}")
        print("Existing keys preserved. Pass --force to replace.")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Failed to initialize keys: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
