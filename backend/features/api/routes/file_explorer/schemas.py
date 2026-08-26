"""SoAI - File explorer mutation request schemas [backend/features/api/routes/file_explorer/schemas.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = (
    "BatchCopyRequest",
    "BatchDeleteRequest",
    "BatchMoveRequest",
    "CopyRequest",
    "DeleteRequest",
    "DownloadSelectionRequest",
    "MkdirRequest",
    "MoveRequest",
    "WriteTextRequest",
)


class WriteTextRequest(BaseModel):
    path: str = Field(description="Virtual file path")
    content: str = Field(description="UTF-8 text content to write")


class MkdirRequest(BaseModel):
    path: str = Field(description="Virtual directory path to create")


class DeleteRequest(BaseModel):
    path: str = Field(description="Virtual path to delete")


class DownloadSelectionRequest(BaseModel):
    paths: list[str] = Field(
        description="Virtual paths to include in one download archive",
        min_length=2,
    )


class MoveRequest(BaseModel):
    source: str = Field(description="Source virtual path")
    destination: str = Field(description="Destination virtual path")
    overwrite: bool = Field(default=False, description="Overwrite destination if it exists")


class CopyRequest(BaseModel):
    source: str = Field(description="Source virtual path")
    destination: str = Field(description="Destination virtual path")
    overwrite: bool = Field(default=False, description="Overwrite destination if it exists")


class BatchDeleteRequest(BaseModel):
    paths: list[str] = Field(description="Virtual paths to delete", min_length=1)


class BatchMoveRequest(BaseModel):
    sources: list[str] = Field(description="Source virtual paths", min_length=1)
    destination_dir: str = Field(description="Destination directory path")
    overwrite: bool = Field(default=False, description="Overwrite destinations if they exist")


class BatchCopyRequest(BaseModel):
    sources: list[str] = Field(description="Source virtual paths", min_length=1)
    destination_dir: str = Field(description="Destination directory path")
    overwrite: bool = Field(default=False, description="Overwrite destinations if they exist")
