/* SoAI - WebUI preview API path builders [frontend/assets/ts/core/api/endpoints/webuiPreviewPaths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const WEBUI_PREVIEWS_BASE_PATH = '/api/v1/webui/previews';
const WEBUI_PREVIEW_PROXY_PATH = `${WEBUI_PREVIEWS_BASE_PATH}/proxy`;
const PROXY_PREFIX = `${WEBUI_PREVIEW_PROXY_PATH}?url=`;

const buildMediaProxyUrl = (url: string, download: boolean): string => {
    const flag = download ? '1' : '0';
    return `${PROXY_PREFIX}${encodeURIComponent(url)}&download=${flag}`;
};

const buildLinkPreviewUrl = (url: string): string => {
    return `${WEBUI_PREVIEWS_BASE_PATH}/link_preview?url=${encodeURIComponent(url)}`;
};

const isMediaProxyUrl = (url: URL): boolean => url.pathname === WEBUI_PREVIEW_PROXY_PATH && url['searchParams'].has('url');

export { PROXY_PREFIX, buildLinkPreviewUrl, buildMediaProxyUrl, isMediaProxyUrl };
