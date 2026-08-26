"""SoAI - Binary storage/data extension constants [backend/core/files/extensions/binaries_extensions_storage_and_data.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

DATABASE_EXTENSIONS = frozenset(
    (
        "accdb",
        "bdb",
        "db",
        "dbf",
        "fdb",
        "frm",
        "gdb",
        "kdb",
        "kdbx",
        "ldb",
        "lmdb",
        "mdb",
        "myd",
        "myi",
        "sqlite",
        "sqlite3",
        "sqlitedb",
        "wallet",
    ),
)

DATA_EXTENSIONS = frozenset(
    (
        "arrow",
        "bson",
        "cbor",
        "feather",
        "h5",
        "hdf",
        "hdf5",
        "msgpack",
        "npy",
        "npz",
        "parquet",
        "pcap",
        "pcapng",
        "tfrecord",
        "xlsb",
    )
)

MODEL_EXTENSIONS = frozenset(
    (
        "gguf",
        "onnx",
        "pb",
        "pt",
        "pth",
        "safetensors",
    )
)

BINARY_STORAGE_EXTENSIONS = frozenset(
    (
        "der",
        "job",
        "keystore",
        "p12",
        "pfb",
        "pfx",
    )
)

BINARY_EXTENSIONS_STORAGE_AND_DATA = frozenset(
    (
        *DATABASE_EXTENSIONS,
        *DATA_EXTENSIONS,
        *MODEL_EXTENSIONS,
        *BINARY_STORAGE_EXTENSIONS,
    )
)
