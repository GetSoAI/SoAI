/* SoAI - Chat feature tool result image rendering [frontend/assets/ts/features/chat/message/messageview/toolResultImageRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { renderImageFigure } from '@features/chat/message/messageview/renderImageFigure.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';
import { buildInlineImageDataUrl, omitToolImageFields, resolveImageDownloadName, resolveToolImageDescriptor, type ToolImagePayload } from '@features/chat/toolactivity/toolImagePayload.ts';

interface ToolResultImageRender {
    consumedKeys: string[];
    html: string;
}

const GENERATED_IMAGE_TOOL_NAME = 'generate_image';
const READ_IMAGE_TOOL_NAME = 'read_image';

const resolveToolImageLabel = (toolLeafName: string): string => {
    if (toolLeafName === GENERATED_IMAGE_TOOL_NAME) {
        return i18n.t('chat.message.generatedImage');
    }
    if (toolLeafName === READ_IMAGE_TOOL_NAME) {
        return i18n.t('chat.toolActivity.image');
    }
    return i18n.t('chat.toolActivity.screenshot');
};

const resolveToolImageDownloadName = (payload: ToolImagePayload, toolLeafName: string): string => {
    if (toolLeafName === GENERATED_IMAGE_TOOL_NAME) {
        return resolveImageDownloadName(payload.contentType, 'soai-generated-image.png');
    }
    if (toolLeafName === READ_IMAGE_TOOL_NAME) {
        return resolveImageDownloadName(payload.contentType, 'soai-image.jpg');
    }
    return 'soai-browser-screenshot.png';
};

const buildToolResultImageHtml = (host: ChatMessageRenderHost, source: string, payload: ToolImagePayload, toolLeafName: string): string =>
    renderImageFigure(host, {
        src: source,
        label: resolveToolImageLabel(toolLeafName),
        className: 'inline-tool-image',
        downloadName: resolveToolImageDownloadName(payload, toolLeafName),
        contentType: payload.contentType,
        contentLength: payload.contentLength,
        loading: toolLeafName === GENERATED_IMAGE_TOOL_NAME ? 'lazy' : 'eager'
    });

const resolveToolResultImageRender = (host: ChatMessageRenderHost, payload: JsonValue | undefined, options: { toolLeafName?: string } = {}): ToolResultImageRender | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const toolLeafName = options.toolLeafName ?? '';
    const imageDescriptor = resolveToolImageDescriptor(payload, { toolLeafName });
    if (imageDescriptor === null) {
        return null;
    }
    const source = buildInlineImageDataUrl(imageDescriptor.payload.contentType, imageDescriptor.payload.imageBase64);
    const html = buildToolResultImageHtml(host, source, imageDescriptor.payload, toolLeafName);
    if (!html) {
        return null;
    }
    return {
        consumedKeys: imageDescriptor.consumedKeys,
        html
    };
};

const omitToolResultImageFields = omitToolImageFields;

export { omitToolResultImageFields, resolveToolResultImageRender };
export type { ToolResultImageRender };
