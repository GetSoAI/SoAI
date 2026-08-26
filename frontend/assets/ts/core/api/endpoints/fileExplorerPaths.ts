/* SoAI - File Explorer API path builders [frontend/assets/ts/core/api/endpoints/fileExplorerPaths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const FILE_EXPLORER_BASE_PATH = '/api/v1/file-explorer';

const buildFileExplorerPreviewUrl = (virtualPath: string, download: boolean): string => {
    const flag = download ? '1' : '0';
    return `${FILE_EXPLORER_BASE_PATH}/preview?path=${encodeURIComponent(virtualPath)}&download=${flag}`;
};

const buildFileExplorerReadUrl = (virtualPath: string): string => {
    return `${FILE_EXPLORER_BASE_PATH}/read?path=${encodeURIComponent(virtualPath)}`;
};

const buildFileExplorerMetadataUrl = (virtualPath: string): string => {
    return `${FILE_EXPLORER_BASE_PATH}/metadata?path=${encodeURIComponent(virtualPath)}&include_hash=0`;
};

const buildFileExplorerListUrl = (virtualPath: string, limit: number): string => {
    return `${FILE_EXPLORER_BASE_PATH}/list?path=${encodeURIComponent(virtualPath)}&offset=0&limit=${encodeURIComponent(String(limit))}`;
};

export { FILE_EXPLORER_BASE_PATH, buildFileExplorerListUrl, buildFileExplorerMetadataUrl, buildFileExplorerPreviewUrl, buildFileExplorerReadUrl };
