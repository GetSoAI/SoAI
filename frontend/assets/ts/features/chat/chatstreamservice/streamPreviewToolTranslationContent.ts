/* SoAI - Chat stream content tool status preview translation [frontend/assets/ts/features/chat/chatstreamservice/streamPreviewToolTranslationContent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { JsonRecord } from '@core/types/jsonValues.ts';

const translateChatStreamContentToolPreviewKey = (previewKey: string, previewArguments: JsonRecord | undefined): string | null => {
    switch (previewKey) {
        case 'chat.stream.preview.tools.base64.1':
            return i18n.t('chat.stream.preview.tools.base64.1', previewArguments).trim();
        case 'chat.stream.preview.tools.browser.1':
            return i18n.t('chat.stream.preview.tools.browser.1', previewArguments).trim();
        case 'chat.stream.preview.tools.browser.2':
            return i18n.t('chat.stream.preview.tools.browser.2', previewArguments).trim();
        case 'chat.stream.preview.tools.browser.detail.1':
            return i18n.t('chat.stream.preview.tools.browser.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.browser.detail.2':
            return i18n.t('chat.stream.preview.tools.browser.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.glob_files.1':
            return i18n.t('chat.stream.preview.tools.glob_files.1', previewArguments).trim();
        case 'chat.stream.preview.tools.glob_files.detail.1':
            return i18n.t('chat.stream.preview.tools.glob_files.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.grep_files.1':
            return i18n.t('chat.stream.preview.tools.grep_files.1', previewArguments).trim();
        case 'chat.stream.preview.tools.grep_files.detail.1':
            return i18n.t('chat.stream.preview.tools.grep_files.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.hash.1':
            return i18n.t('chat.stream.preview.tools.hash.1', previewArguments).trim();
        case 'chat.stream.preview.tools.http_request.1':
            return i18n.t('chat.stream.preview.tools.http_request.1', previewArguments).trim();
        case 'chat.stream.preview.tools.http_request.2':
            return i18n.t('chat.stream.preview.tools.http_request.2', previewArguments).trim();
        case 'chat.stream.preview.tools.http_request.detail.1':
            return i18n.t('chat.stream.preview.tools.http_request.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.http_request.detail.2':
            return i18n.t('chat.stream.preview.tools.http_request.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.list_dir.1':
            return i18n.t('chat.stream.preview.tools.list_dir.1', previewArguments).trim();
        case 'chat.stream.preview.tools.list_dir.detail.1':
            return i18n.t('chat.stream.preview.tools.list_dir.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.news.1':
            return i18n.t('chat.stream.preview.tools.news.1', previewArguments).trim();
        case 'chat.stream.preview.tools.news.detail.1':
            return i18n.t('chat.stream.preview.tools.news.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_audio.1':
            return i18n.t('chat.stream.preview.tools.read_audio.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_document.1':
            return i18n.t('chat.stream.preview.tools.read_document.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_document.2':
            return i18n.t('chat.stream.preview.tools.read_document.2', previewArguments).trim();
        case 'chat.stream.preview.tools.read_document.detail.1':
            return i18n.t('chat.stream.preview.tools.read_document.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_document.detail.2':
            return i18n.t('chat.stream.preview.tools.read_document.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.read_file.1':
            return i18n.t('chat.stream.preview.tools.read_file.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_file.2':
            return i18n.t('chat.stream.preview.tools.read_file.2', previewArguments).trim();
        case 'chat.stream.preview.tools.read_file.detail.1':
            return i18n.t('chat.stream.preview.tools.read_file.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_file.detail.2':
            return i18n.t('chat.stream.preview.tools.read_file.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.read_image.1':
            return i18n.t('chat.stream.preview.tools.read_image.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_image.2':
            return i18n.t('chat.stream.preview.tools.read_image.2', previewArguments).trim();
        case 'chat.stream.preview.tools.read_image.detail.1':
            return i18n.t('chat.stream.preview.tools.read_image.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_image.detail.2':
            return i18n.t('chat.stream.preview.tools.read_image.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.read_video.1':
            return i18n.t('chat.stream.preview.tools.read_video.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_video.2':
            return i18n.t('chat.stream.preview.tools.read_video.2', previewArguments).trim();
        case 'chat.stream.preview.tools.read_video.detail.1':
            return i18n.t('chat.stream.preview.tools.read_video.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.read_video.detail.2':
            return i18n.t('chat.stream.preview.tools.read_video.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.replace_in_file.1':
            return i18n.t('chat.stream.preview.tools.replace_in_file.1', previewArguments).trim();
        case 'chat.stream.preview.tools.replace_in_file.detail.1':
            return i18n.t('chat.stream.preview.tools.replace_in_file.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.rss_read.1':
            return i18n.t('chat.stream.preview.tools.rss_read.1', previewArguments).trim();
        case 'chat.stream.preview.tools.rss_read.detail.1':
            return i18n.t('chat.stream.preview.tools.rss_read.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.weather.1':
            return i18n.t('chat.stream.preview.tools.weather.1', previewArguments).trim();
        case 'chat.stream.preview.tools.web_fetch.1':
            return i18n.t('chat.stream.preview.tools.web_fetch.1', previewArguments).trim();
        case 'chat.stream.preview.tools.web_fetch.2':
            return i18n.t('chat.stream.preview.tools.web_fetch.2', previewArguments).trim();
        case 'chat.stream.preview.tools.web_fetch.detail.1':
            return i18n.t('chat.stream.preview.tools.web_fetch.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.web_fetch.detail.2':
            return i18n.t('chat.stream.preview.tools.web_fetch.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_web_fetch.1':
            return i18n.t('chat.stream.preview.tools.knowledge_web_fetch.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_web_fetch.detail.1':
            return i18n.t('chat.stream.preview.tools.knowledge_web_fetch.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.web_search.1':
            return i18n.t('chat.stream.preview.tools.web_search.1', previewArguments).trim();
        case 'chat.stream.preview.tools.web_search.2':
            return i18n.t('chat.stream.preview.tools.web_search.2', previewArguments).trim();
        case 'chat.stream.preview.tools.web_search.detail.1':
            return i18n.t('chat.stream.preview.tools.web_search.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.web_search.detail.2':
            return i18n.t('chat.stream.preview.tools.web_search.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.write_file.1':
            return i18n.t('chat.stream.preview.tools.write_file.1', previewArguments).trim();
        case 'chat.stream.preview.tools.write_file.detail.1':
            return i18n.t('chat.stream.preview.tools.write_file.detail.1', previewArguments).trim();
        default:
            return null;
    }
};

export { translateChatStreamContentToolPreviewKey };
