"""Download the released roof model into models/ and verify its checksum.

Usage (from the repo root): python backend/scripts/fetch_model.py
Standard library only, so it runs with any Python 3.11+.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

NAME = "roof_unet_r18_gsd015_v0.1.0.onnx"
URL = f"https://github.com/lynnbanna/wattwatch/releases/download/model-v0.1.0/{NAME}"
SHA256 = "f3eb427e94c1e467d12ba9b6283f5a0e0ab5edd9f8d79ca36e4bca346bb40e66"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    target = Path(__file__).resolve().parents[2] / "models" / NAME
    if target.is_file() and sha256(target) == SHA256:
        print(f"{target} already present and verified")
        return
    partial = target.with_suffix(".part")
    print(f"downloading {URL}")
    urllib.request.urlretrieve(URL, partial)
    if sha256(partial) != SHA256:
        partial.unlink()
        sys.exit("checksum mismatch; download discarded")
    partial.replace(target)
    print(f"saved {target}")


if __name__ == "__main__":
    main()
