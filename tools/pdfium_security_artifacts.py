"""Build PDFium security wheels with matching native headers [release_tools/pdfium_security_artifacts.py]"""
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
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_member(name: str, names: set[str]) -> None:
    normalized = unicodedata.normalize("NFC", name.rstrip("/")).casefold()
    if (
        not name
        or "\\" in name
        or any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))
        or ":" in name.split("/", 1)[0]
        or normalized in names
    ):
        raise ValueError("PDFium archive has an unsafe or duplicate member")
    names.add(normalized)


def acquire_input(record: dict[str, str], cache: Path) -> Path:
    filename = record["filename"]
    if Path(filename).name != filename or "\\" in filename:
        raise ValueError("PDFium input filename must be one path component")
    parsed = urllib.parse.urlsplit(record["url"])
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ("files.pythonhosted.org", "github.com")
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.query
        or parsed.port not in (None, 443)
    ):
        raise ValueError("PDFium inputs must use their official HTTPS publishers")
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / filename
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise ValueError("PDFium cached input must be a regular file")
        if digest(destination) != record["sha256"]:
            raise ValueError("PDFium cached input digest mismatch")
        return destination
    with tempfile.NamedTemporaryFile(dir=cache, prefix=".pdfium-input-", delete=False) as output:
        temporary = Path(output.name)
        try:
            with urllib.request.urlopen(record["url"], timeout=90) as response:
                resolved = urllib.parse.urlsplit(response.url)
                if resolved.scheme != "https" or resolved.hostname not in (
                    "files.pythonhosted.org",
                    "github.com",
                    "release-assets.githubusercontent.com",
                ):
                    raise ValueError("PDFium download redirected outside its publishers")
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 32 * 1024 * 1024:
                        raise ValueError("PDFium input exceeds its size budget")
                    output.write(chunk)
            output.flush()
            if digest(temporary) != record["sha256"]:
                raise ValueError("PDFium downloaded input digest mismatch")
            temporary.rename(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def extract_input(archive_path: Path, destination: Path) -> None:
    names: set[str] = set()
    with tarfile.open(archive_path) as archive:
        total = 0
        for member in archive.getmembers():
            validate_member(member.name, names)
            total += member.size
            if total > 64 * 1024 * 1024 or not (member.isfile() or member.isdir()):
                raise ValueError("PDFium source archive has invalid members or exceeds its budget")
        archive.extractall(destination, filter="data")


def publish_wheel(artifact: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / artifact.name
    expected_digest = digest(artifact)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or digest(target) != expected_digest:
            raise ValueError("Refusing to overwrite a different PDFium artifact")
        return target
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination, prefix=".pdfium-wheel-", delete=False
        ) as output:
            temporary = Path(output.name)
            with artifact.open("rb") as source:
                shutil.copyfileobj(source, output)
            os.chmod(temporary, 0o644)
            output.flush()
            os.fsync(output.fileno())
        if digest(temporary) != expected_digest:
            raise ValueError("PDFium staged artifact digest mismatch")
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.is_symlink() or not target.is_file() or digest(target) != expected_digest:
                raise ValueError("Refusing to overwrite a different PDFium artifact") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    if os.name != "nt":
        directory_descriptor = os.open(destination, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    return target


def build_wheel(
    catalog: dict,
    platform: dict,
    cache: Path,
    destination: Path,
) -> Path:
    source_archive = acquire_input(catalog["source"], cache)
    upstream_wheel = acquire_input(platform["wheel"], cache)
    native_archive = acquire_input(platform["native"], cache)
    environment = dict(os.environ, SOURCE_DATE_EPOCH="315532800", TZ="UTC", PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory(prefix="pdfium-security-") as temporary:
        stage = Path(temporary)
        extract_input(source_archive, stage / "source")
        source = stage / "source" / "pypdfium2-5.14.0"
        if not (source / "deps/ctypesgen/src/ctypesgen/__main__.py").is_file():
            raise ValueError("PDFium source must contain its matching upstream ctypesgen")
        native = stage / "native"
        extract_input(native_archive, native)
        native_version = dict(
            line.split("=", 1) for line in (native / "VERSION").read_text().splitlines()
        )
        if native_version != {"MAJOR": "158", "MINOR": "0", "BUILD": "8111", "PATCH": "0"}:
            raise ValueError("PDFium binary has an unexpected native version")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "wheel",
                "unpack",
                str(upstream_wheel),
                "-d",
                str(stage / "wheel"),
            ],
            check=True,
            timeout=120,
            env=environment,
        )
        (package,) = (stage / "wheel").iterdir()
        raw = package / "pypdfium2_raw"
        binding_command = (
            "import sys; from pathlib import Path; sys.path.insert(0, 'setupsrc'); "
            "from base import run_ctypesgen; "
            "run_ctypesgen(Path(sys.argv[1]), Path(sys.argv[2]), "
            "no_srcinfo=True, windows_cross=sys.argv[3]=='windows-x64', version=8111)"
        )
        subprocess.run(
            [
                sys.executable,
                "-c",
                binding_command,
                str(raw / "bindings.py"),
                str(native / "include"),
                platform["platform"],
            ],
            cwd=source,
            check=True,
            timeout=120,
            env=environment,
        )
        bindings_path = raw / "bindings.py"
        bindings = bindings_path.read_text(encoding="utf-8")
        opening, generation_record, implementation = bindings.split('"""', 2)
        if opening != "R" or str(stage) in implementation:
            raise ValueError("Generated PDFium bindings have unexpected provenance or build paths")
        bindings_path.write_text(
            f'R"""{generation_record.replace(str(stage), "<BUILD_ROOT>")}"""{implementation}',
            encoding="utf-8",
        )
        shutil.copyfile(native / platform["binary"], raw / Path(platform["binary"]).name)
        (raw / "version.json").write_text(
            json.dumps(
                {
                    "major": 158,
                    "minor": 0,
                    "build": 8111,
                    "patch": 0,
                    "n_commits": 0,
                    "hash": None,
                    "origin": "pdfium-binaries-soai",
                    "flags": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (metadata,) = package.glob("*.dist-info")
        text = (metadata / "METADATA").read_text(encoding="utf-8")
        if text.count("\nVersion: 5.14.0\n") != 1:
            raise ValueError("Unexpected upstream pypdfium2 package version")
        license_directories = tuple((metadata / "licenses").rglob("BUILD_LICENSES"))
        if len(license_directories) != 1:
            raise ValueError("Upstream pypdfium2 wheel has no native license inventory")
        (license_directory,) = license_directories
        shutil.rmtree(license_directory)
        shutil.copytree(native / "licenses", license_directory)
        shutil.copyfile(native / "LICENSE", license_directory / "pdfium-binaries.txt")
        license_prefix = license_directory.relative_to(metadata / "licenses").as_posix()
        retained_lines = [
            line
            for line in text.splitlines(keepends=True)
            if not line.startswith(f"License-File: {license_prefix}/")
        ]
        text = "".join(retained_lines).replace("\nVersion: 5.14.0\n", "\nVersion: 5.14.0+soai.1\n")
        header, separator, body = text.partition("\n\n")
        if not separator:
            raise ValueError("Upstream pypdfium2 wheel has no metadata header boundary")
        native_licenses = "".join(
            f"License-File: {license_prefix}/{member.name}\n"
            for member in sorted(license_directory.iterdir())
        )
        (metadata / "METADATA").write_text(f"{header}\n{native_licenses}\n{body}", encoding="utf-8")
        (metadata / "PDFIUM-SoAI-build.json").write_text(
            json.dumps(
                {
                    "package_version": "5.14.0+soai.1",
                    "native_version": "158.0.8111.0",
                    "builder_sha256": digest(Path(__file__)),
                    "corrected_advisories": ["CVE-2026-110155"],
                    "source": catalog["source"],
                    "platform_inputs": platform,
                    "bindings_sha256": digest(raw / "bindings.py"),
                    "native_sha256": digest(raw / Path(platform["binary"]).name),
                    "v8_enabled": False,
                    "xfa_enabled": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        metadata.rename(package / "pypdfium2-5.14.0+soai.1.dist-info")
        for member in package.rglob("*"):
            os.utime(member, (315532800, 315532800))
            os.chmod(member, 0o755 if member.is_dir() else 0o644)
        output = stage / "output"
        output.mkdir()
        subprocess.run(
            [sys.executable, "-m", "wheel", "pack", str(package), "-d", str(output)],
            check=True,
            timeout=120,
            env=environment,
        )
        (artifact,) = output.iterdir()
        upstream_tags = platform["wheel"]["filename"].removesuffix(".whl").rsplit("-", 1)[1]
        canonical_tags = ".".join(sorted(upstream_tags.split(".")))
        expected_name = f"pypdfium2-5.14.0+soai.1-py3-none-{canonical_tags}.whl"
        if artifact.name != expected_name:
            raise ValueError("PDFium build produced an unexpected wheel tag or identity")
        return publish_wheel(artifact, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--input-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    catalog = json.loads(arguments.catalog.read_text(encoding="utf-8"))
    if catalog["package_version"] != "5.14.0+soai.1" or catalog["native_version"] != "158.0.8111.0":
        raise ValueError("PDFium catalog does not identify the authorized target")
    if digest(Path(__file__)) != catalog["builder_sha256"]:
        raise ValueError("PDFium builder differs from its recorded build input")
    for platform in catalog["platforms"]:
        with tempfile.TemporaryDirectory(prefix="pdfium-verification-") as temporary:
            artifact = build_wheel(
                catalog, platform, arguments.input_cache.resolve(), Path(temporary)
            )
            if digest(artifact) != catalog["artifacts"][artifact.name]:
                raise ValueError("PDFium rebuilt artifact differs from its recorded digest")
            publish_wheel(artifact, arguments.output)
            print(f"Verified {artifact.name}: {digest(artifact)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
