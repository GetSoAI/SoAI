/* SoAI - Chat feature assistant generated image widget [frontend/assets/ts/features/chat/message/messageview/assistantGeneratedImageWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderImageFigure } from '@features/chat/message/messageview/renderImageFigure.ts';
import type { ChatMessageRenderHost, MessageSegment } from '@features/chat/message/messageview/types.ts';
import { buildInlineImageDataUrl, resolveImageDownloadName, resolveToolImagePayload } from '@features/chat/toolactivity/toolImagePayload.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

const GENERATED_IMAGE_TOOL_NAME = 'generate_image';

const renderAssistantGeneratedImageWidget = (host: ChatMessageRenderHost, segment: MessageSegment): string => {
    if (segment.type !== 'inline_tool_activity') {
        return '';
    }
    const toolLeafName = normalizeToolLeafName(segment.toolName);
    if (segment.status !== 'completed' || toolLeafName !== GENERATED_IMAGE_TOOL_NAME) {
        return '';
    }
    const payload = resolveToolImagePayload(segment.result);
    if (payload === null) {
        return '';
    }
    const source = buildInlineImageDataUrl(payload.contentType, payload.imageBase64);
    return renderImageFigure(host, {
        src: source,
        label: i18n.t('chat.message.generatedImage'),
        className: 'assistant-activity-widget-image',
        downloadName: resolveImageDownloadName(payload.contentType, 'soai-generated-image.png'),
        contentType: payload.contentType,
        contentLength: payload.contentLength
    });
};

export { renderAssistantGeneratedImageWidget };
