"""Reproduce patched dependency artifacts from verified upstream inputs [release_tools/dependency_security_artifacts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def exclude_ignore_files(package: Path) -> None:
    for member in sorted(package.rglob("*"), key=lambda path: len(path.parts), reverse=True):
        if member.name.casefold() in (".gitignore", ".gtignore"):
            if member.is_dir():
                shutil.rmtree(member)
            else:
                member.unlink()


def validate_member(name: str, names: set[str]) -> None:
    parts = name.rstrip("/").split("/")
    if (
        not name
        or "\\" in name
        or any(part in ("", ".", "..") for part in parts)
        or ":" in parts[0]
        or unicodedata.normalize("NFC", name.rstrip("/")).casefold() in names
    ):
        raise ValueError(f"Unsafe or duplicate upstream archive member: {name}")
    names.add(unicodedata.normalize("NFC", name.rstrip("/")).casefold())


def validate_archive(path: Path, ecosystem: str) -> None:
    names: set[str] = set()
    total = 0
    if ecosystem == "PyPI":
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                total += member.file_size
                if total > 2_000_000_000 or member.file_size > 500_000_000:
                    raise ValueError("Upstream wheel exceeds its extraction size budget")
                validate_member(member.filename, names)
                mode = member.external_attr >> 16
                if mode & 0o170000 not in (0, 0o100000, 0o040000):
                    raise ValueError("Upstream wheel contains a nonregular member")
    elif ecosystem == "npm":
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                total += member.size
                if total > 2_000_000_000 or member.size > 500_000_000:
                    raise ValueError("Upstream package exceeds its extraction size budget")
                validate_member(member.name, names)
                if not (member.isfile() or member.isdir()):
                    raise ValueError("Upstream package contains a nonregular member")
                if member.name.split("/", 1)[0] != "package":
                    raise ValueError("Upstream npm package has an unexpected root")
    else:
        raise ValueError(f"Unknown ecosystem: {ecosystem}")


def fetch_source(url: str, expected_digest: str, destination: Path) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in (
        "files.pythonhosted.org",
        "registry.npmjs.org",
    ):
        raise ValueError("Dependency source must use its official HTTPS registry")
    if parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError("Invalid dependency source URL")
    with urllib.request.urlopen(url, timeout=60) as response:
        if response.url != url:
            raise ValueError("Dependency source redirected")
        with destination.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 1_000_000_000:
                    raise ValueError("Dependency source exceeds its size budget")
                output.write(chunk)
    if digest(destination) != expected_digest:
        raise ValueError("Upstream dependency digest mismatch")


def build_artifact(
    repository: Path, entry: dict[str, str], destination: Path, *, verify: bool = True
) -> Path:
    patch = repository / entry["patch"]
    if verify and digest(Path(__file__)) != entry["builder_sha256"]:
        raise ValueError("Dependency builder differs from its recorded build input")
    if patch.is_symlink() or not patch.resolve(strict=True).is_relative_to(repository.resolve()):
        raise ValueError("Dependency patch must be a regular repository input")
    for field in ("source_filename", "artifact_filename"):
        if Path(entry[field]).name != entry[field] or "\\" in entry[field]:
            raise ValueError("Dependency artifact filenames must be single path components")
    if digest(patch) != entry["patch_sha256"]:
        raise ValueError("Dependency patch digest mismatch")
    destination.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, SOURCE_DATE_EPOCH="315532800", TZ="UTC", PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory(prefix="dependency-artifact-") as temporary:
        stage = Path(temporary)
        source = stage / entry["source_filename"]
        fetch_source(entry["source_url"], entry["source_sha256"], source)
        validate_archive(source, entry["ecosystem"])
        if entry["ecosystem"] == "PyPI":
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wheel",
                    "unpack",
                    str(source),
                    "--dest",
                    str(stage / "unpacked"),
                ],
                check=True,
                timeout=120,
                env=environment,
            )
            unpacked = tuple((stage / "unpacked").iterdir())
            if len(unpacked) != 1:
                raise ValueError("Wheel unpack produced an unexpected inventory")
            package = unpacked[0]
        else:
            with tarfile.open(source, "r:gz") as archive:
                archive.extractall(stage / "unpacked", filter="data")
            package = stage / "unpacked" / "package"
        carriage_return_sources: list[Path] = []
        for line in patch.read_text(encoding="utf-8").splitlines():
            if line.startswith("+++ b/"):
                relative = line.removeprefix("+++ b/")
                validate_member(relative, set())
                member = package / relative
                content = member.read_bytes()
                if b"\r\n" in content and b"\n" not in content.replace(b"\r\n", b""):
                    member.write_bytes(content.replace(b"\r\n", b"\n"))
                    carriage_return_sources.append(member)
        subprocess.run(
            ["patch", "--batch", "--fuzz=0", "--no-backup-if-mismatch", "-p1", "-i", str(patch)],
            cwd=package,
            env=environment,
            check=True,
            timeout=60,
        )
        for member in carriage_return_sources:
            member.write_bytes(member.read_bytes().replace(b"\n", b"\r\n"))
        exclude_ignore_files(package)
        (stage / "output").mkdir()
        if entry["ecosystem"] == "PyPI":
            metadata = tuple(package.glob("*.dist-info"))
            if len(metadata) != 1:
                raise ValueError("Wheel has an unexpected metadata inventory")
            distribution = metadata[0].name.split("-", 1)[0]
            metadata[0].rename(package / f"{distribution}-{entry['version']}.dist-info")
            for payload in package.glob("*.data"):
                payload.rename(package / f"{distribution}-{entry['version']}.data")
            for member in package.rglob("*"):
                os.utime(member, (315532800, 315532800))
            command = [
                sys.executable,
                "-m",
                "wheel",
                "pack",
                str(package),
                "--dest-dir",
                str(stage / "output"),
            ]
        else:
            command = [
                "npm",
                "pack",
                "--silent",
                "--ignore-scripts",
                "--pack-destination",
                str(stage / "output"),
            ]
        subprocess.run(command, cwd=package, env=environment, check=True, timeout=120)
        built = tuple((stage / "output").iterdir())
        if len(built) != 1 or built[0].name != entry["artifact_filename"]:
            raise ValueError("Dependency build produced an unexpected artifact")
        if verify and digest(built[0]) != entry["artifact_sha256"]:
            raise ValueError("Rebuilt dependency does not match its recorded artifact")
        target = destination / built[0].name
        if target.exists() and digest(target) != digest(built[0]):
            raise ValueError(f"Refusing to overwrite a different artifact: {target}")
        target.write_bytes(built[0].read_bytes())
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    entries = json.loads(arguments.catalog.read_text(encoding="utf-8"))
    for entry in entries:
        target = build_artifact(
            arguments.repository_root.resolve(), entry, arguments.output.resolve()
        )
        print(f"Verified {target.name}: {digest(target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
