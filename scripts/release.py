#!/usr/bin/env python3
"""Pack, sign and list this repository's pokeldn plugins.

    python scripts/release.py swsh-den-seed            # dist/swsh-den-seed-1.0.0.pokeplugin + listing
    python scripts/release.py --all
    python scripts/release.py swsh-den-seed --check    # verify an existing package against its files

The signature and the listing follow pokeldn's `pokeldn/app/plugin_store.py` and docs/plugins.md:
`plugin.sig` is the author's Ed25519 public key and a signature over the plugin id, version and the
SHA-256 of every packed file; `pokeldn-source.json` is the source listing players follow. The private
key is created on first use at --key (default ~/.pokeldn-signing.pem): back it up, never commit it.
Needs pycryptodome (pip install pycryptodome).
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
DIST = ROOT / "dist"
LISTING = ROOT / "pokeldn-source.json"
SOURCE = ROOT / "source.toml"              # the listing's name, homepage and download template
SIGNATURE = "plugin.sig"
SKIP = ("__pycache__", ".DS_Store", ".installed.json", SIGNATURE)
SIGNED = b"pokeldn plugin signature 1\n"


def files_of(folder: Path, exclude=()) -> dict:
    """Relative POSIX name -> bytes, as pokeldn installs them: no hidden names, no SKIP parts."""
    out = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        rel = PurePosixPath(path.relative_to(folder).as_posix())
        if any(part in SKIP or part.startswith(".") for part in rel.parts):
            continue
        if any(rel.parts[0] == ex for ex in exclude):
            continue
        out[str(rel)] = path.read_bytes()
    return out


def manifest(plugin_id: str, version: str, files: dict) -> bytes:
    lines = sorted(f"{hashlib.sha256(data).hexdigest()}  {name}" for name, data in files.items()
                   if name and not any(part in SKIP for part in PurePosixPath(name).parts))
    return SIGNED + f"{plugin_id}\n{version}\n".encode() + "\n".join(lines).encode()


def signing_key(path: Path):
    from Crypto.PublicKey import ECC
    if not path.exists():
        key = ECC.generate(curve="ed25519")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "x", encoding="utf-8") as out:
            out.write(key.export_key(format="PEM"))
        if os.name != "nt":
            os.chmod(path, 0o600)
        print(f"created the signing key {path}: back it up and keep it private")
        return key
    return ECC.import_key(path.read_text(encoding="utf-8"))


def fingerprint(raw_public: bytes) -> str:
    text = base64.b32encode(hashlib.sha256(raw_public).digest()).decode()[:16]
    return "-".join(text[i:i + 4] for i in range(0, 16, 4))


def sign(key, plugin_id: str, version: str, files: dict) -> bytes:
    from Crypto.Signature import eddsa
    raw = key.public_key().export_key(format="raw")
    signature = eddsa.new(key, "rfc8032").sign(manifest(plugin_id, version, files))
    return json.dumps({"key": base64.b64encode(raw).decode(),
                       "signature": base64.b64encode(signature).decode()}).encode()


def verify(plugin_id: str, version: str, files: dict) -> str:
    """The signer's fingerprint, or raises."""
    from Crypto.Signature import eddsa
    signed = json.loads(files[SIGNATURE])
    raw = base64.b64decode(signed["key"], validate=True)
    eddsa.new(eddsa.import_public_key(raw), "rfc8032").verify(
        manifest(plugin_id, version, files), base64.b64decode(signed["signature"], validate=True))
    return fingerprint(raw)


def meta_of(folder: Path) -> dict:
    meta = tomllib.loads((folder / "plugin.toml").read_text(encoding="utf-8"))
    for key in ("id", "name", "version", "api"):
        if not meta.get(key):
            raise SystemExit(f"{folder.name}/plugin.toml lacks {key}")
    if meta["id"] != folder.name:
        raise SystemExit(f"{folder.name}: the folder is named after the id, which is {meta['id']!r}")
    return meta


def package_files(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}


def pack(folder: Path, key, dist: Path) -> tuple[Path, dict]:
    meta = meta_of(folder)
    files = files_of(folder, exclude=meta.get("exclude", ()))
    files[SIGNATURE] = sign(key, meta["id"], meta["version"], files)
    dist.mkdir(exist_ok=True)
    out = dist / f"{meta['id']}-{meta['version']}.pokeplugin"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            z.writestr(name, files[name])
    print(f"{out.name}: {len(files) - 1} files, signed by {verify(meta['id'], meta['version'], package_files(out))}")
    return out, meta


def source_config() -> dict:
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE.name} is missing: name, homepage and download template of the listing")
    cfg = tomllib.loads(SOURCE.read_text(encoding="utf-8"))
    for key in ("name", "homepage", "download"):
        if not cfg.get(key):
            raise SystemExit(f"{SOURCE.name} lacks {key}")
    return cfg


def list_entry(package: Path, meta: dict, cfg: dict) -> dict:
    data = package.read_bytes()
    entry = {"id": meta["id"], "name": meta["name"], "version": meta["version"], "api": str(meta["api"]),
             "description": meta.get("description", ""), "author": meta.get("author", ""),
             "download": cfg["download"].format(id=meta["id"], version=meta["version"], file=package.name),
             "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    if meta.get("homepage"):
        entry["homepage"] = meta["homepage"]
    return entry


def update_listing(entries: list, cfg: dict) -> None:
    listing = {"schema": 1, "name": cfg["name"], "homepage": cfg["homepage"], "plugins": []}
    if LISTING.exists():
        listing = json.loads(LISTING.read_text(encoding="utf-8"))
        listing.update(schema=1, name=cfg["name"], homepage=cfg["homepage"])
    by_id = {p["id"]: p for p in listing.get("plugins", [])}
    for entry in entries:
        by_id[entry["id"]] = entry
    listing["plugins"] = [by_id[k] for k in sorted(by_id)]
    LISTING.write_text(json.dumps(listing, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{LISTING.name}: {len(listing['plugins'])} plugin(s) listed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plugins", nargs="*", help="plugin ids under plugins/")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--key", default=os.path.join(os.path.expanduser("~"), ".pokeldn-signing.pem"))
    ap.add_argument("--check", action="store_true", help="verify dist packages against the sources, change nothing")
    ap.add_argument("--no-listing", action="store_true", help="pack and sign only")
    args = ap.parse_args()
    ids = sorted(p.name for p in PLUGINS.iterdir() if (p / "plugin.toml").exists()) if args.all else args.plugins
    if not ids:
        ap.error("name a plugin or pass --all")
    folders = [PLUGINS / i for i in ids]
    for folder in folders:
        if not (folder / "plugin.toml").exists():
            raise SystemExit(f"no plugin at {folder}")
    if args.check:
        for folder in folders:
            meta = meta_of(folder)
            package = DIST / f"{meta['id']}-{meta['version']}.pokeplugin"
            files = package_files(package)
            same = {k: v for k, v in files.items() if k != SIGNATURE} == files_of(folder, meta.get("exclude", ()))
            print(f"{package.name}: signed by {verify(meta['id'], meta['version'], files)}, "
                  f"{'matches' if same else 'DIFFERS FROM'} plugins/{meta['id']}")
        return
    key = signing_key(Path(args.key))
    print(f"signing key fingerprint {fingerprint(key.public_key().export_key(format='raw'))}")
    packed = [pack(folder, key, DIST) for folder in folders]
    if not args.no_listing:
        cfg = source_config()
        update_listing([list_entry(p, m, cfg) for p, m in packed], cfg)


if __name__ == "__main__":
    main()
