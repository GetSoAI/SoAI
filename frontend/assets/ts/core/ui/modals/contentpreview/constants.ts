/* SoAI - Unified content preview modal constants [frontend/assets/ts/core/ui/modals/contentpreview/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export const CONTENT_PREVIEW_MODAL_ID = 'content-preview-modal';
export const CONTENT_PREVIEW_SERVICE_ID = 'core.contentPreviewModal';

export const CONTENT_PREVIEW_ACTION_ATTR = 'data-content-preview-action';

export const CONTENT_PREVIEW_ACTIONS = Object.freeze({
    CLOSE: 'close',
    DOWNLOAD: 'download',
    COPY: 'copy',
    ATTACH: 'attach',
    OPEN_SOURCE: 'openSource',
    EDIT: 'edit',
    SAVE: 'save',
    ENHANCE: 'enhance',
    IMAGE_PREVIOUS: 'imagePrevious',
    IMAGE_NEXT: 'imageNext'
});

export type ContentPreviewAction = (typeof CONTENT_PREVIEW_ACTIONS)[keyof typeof CONTENT_PREVIEW_ACTIONS];

export const CONTENT_PREVIEW_UI_TOKENS = Object.freeze({
    TITLE: 'title',
    DESCRIPTION: 'description',
    COLOR_CONTAINER: 'color-container',
    HEADER_CLOSE: 'header-close',
    FOOTER: 'footer',
    TEXT_HOST: 'text',
    TEXT_STATS: 'text-stats',
    MEDIA_HOST: 'media',
    CLOSE: 'close',
    DOWNLOAD: 'download',
    COPY: 'copy',
    ATTACH: 'attach',
    OPEN_SOURCE: 'open-source',
    EDIT: 'edit',
    SAVE: 'save',
    ENHANCE: 'enhance'
});
