/* SoAI - MCP read_video result media rendering [frontend/assets/ts/features/chat/message/messageview/toolResultReadVideoRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';
import { buildInlineImageDataUrl, resolveToolImagePayload, type ToolImagePayload } from '@features/chat/toolactivity/toolImagePayload.ts';
import { buildInlineVideoDataUrl, resolveToolVideoDescriptor, type ToolVideoPayload } from '@features/chat/toolactivity/toolVideoPayload.ts';

interface ReadVideoResultRender {
    consumedKeys: string[];
    html: string;
    transcriptConsumed: boolean;
}

const READ_VIDEO_FRAME_LIMIT = 18;

const renderVideoPreview = (host: ChatMessageRenderHost, payload: ToolVideoPayload): string => {
    const source = buildInlineVideoDataUrl(payload.contentType, payload.videoBase64);
    const escapedSource = host.escapeAttribute(source);
    const escapedContentType = host.escapeAttribute(payload.contentType);
    const label = host.escapeHtml(i18n.t('chat.toolActivity.video'));
    const video = `<video class="inline-tool-video-player" controls preload="metadata" playsinline><source src="${escapedSource}" type="${escapedContentType}"/></video>`;
    return `<figure class="inline-tool-video"><figcaption>${label}</figcaption>${video}</figure>`;
};

const resolveFrameTimestampText = (frame: JsonObject): string => {
    const value = frame['timestamp_seconds'];
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return '';
    }
    return `${value.toFixed(2)}s`;
};

const renderFrameImage = (host: ChatMessageRenderHost, frame: JsonObject, payload: ToolImagePayload): string => {
    const source = buildInlineImageDataUrl(payload.contentType, payload.imageBase64);
    const sanitizedSource = host.sanitizeImage(source);
    if (!sanitizedSource) {
        return '';
    }
    const timestampText = resolveFrameTimestampText(frame);
    const label = timestampText ? `<figcaption>${host.escapeHtml(timestampText)}</figcaption>` : '';
    return `<figure class="inline-tool-video-frame"><img src="${host.escapeAttribute(sanitizedSource)}" alt="${host.escapeAttribute(timestampText)}" loading="lazy" decoding="async"/>${label}</figure>`;
};

const renderFrameGrid = (host: ChatMessageRenderHost, payload: JsonValue | undefined): string => {
    if (!isJsonArray(payload)) {
        return '';
    }
    const frameHtml: string[] = [];
    for (const frame of payload) {
        if (!isJsonObject(frame)) {
            continue;
        }
        const imagePayload = resolveToolImagePayload(frame, { toolLeafName: 'read_video' });
        if (imagePayload === null) {
            continue;
        }
        const html = renderFrameImage(host, frame, imagePayload);
        if (html) {
            frameHtml.push(html);
        }
        if (frameHtml.length >= READ_VIDEO_FRAME_LIMIT) {
            break;
        }
    }
    if (frameHtml.length === 0) {
        return '';
    }
    const label = host.escapeHtml(i18n.t('chat.toolActivity.videoFrames'));
    return `<section class="inline-tool-video-frames"><div class="inline-tool-media-heading">${label}</div><div class="inline-tool-video-frame-grid">${frameHtml.join('')}</div></section>`;
};

const resolveTranscript = (payload: JsonValue | undefined): string | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const audio = payload['audio'];
    if (!isJsonObject(audio)) {
        return null;
    }
    const transcript = audio['transcript'];
    if (!isString(transcript)) {
        return null;
    }
    const trimmed = transcript.trim();
    return trimmed ? trimmed : null;
};

const renderTranscript = (host: ChatMessageRenderHost, transcript: string | null): string => {
    if (transcript === null) {
        return '';
    }
    const label = host.escapeHtml(i18n.t('chat.toolActivity.transcript'));
    return `<section class="inline-tool-video-transcript"><div class="inline-tool-media-heading">${label}</div><pre class="inline-tool-video-transcript-text">${host.escapeHtml(transcript)}</pre></section>`;
};

const resolveReadVideoResultRender = (host: ChatMessageRenderHost, payload: JsonValue | undefined): ReadVideoResultRender | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const sections: string[] = [];
    const consumedKeys: string[] = [];
    const videoDescriptor = resolveToolVideoDescriptor(payload);
    if (videoDescriptor !== null) {
        sections.push(renderVideoPreview(host, videoDescriptor.payload));
        consumedKeys.push(...videoDescriptor.consumedKeys);
    }
    const framesHtml = renderFrameGrid(host, payload['frames']);
    if (framesHtml) {
        sections.push(framesHtml);
        consumedKeys.push('frames');
    }
    const transcript = resolveTranscript(payload);
    const transcriptHtml = renderTranscript(host, transcript);
    if (transcriptHtml) {
        sections.push(transcriptHtml);
    }
    if (sections.length === 0) {
        return null;
    }
    return {
        consumedKeys,
        html: sections.join(''),
        transcriptConsumed: transcript !== null
    };
};

const filterAudioRecord = (audio: JsonObject, transcriptConsumed: boolean): JsonObject | null => {
    const filtered: JsonObject = {};
    for (const [key, value] of Object.entries(audio)) {
        if (transcriptConsumed && (key === 'transcript' || key === 'segments')) {
            continue;
        }
        filtered[key] = value;
    }
    return Object.keys(filtered).length > 0 ? filtered : null;
};

const omitReadVideoResultFields = (payload: JsonValue | undefined, render: ReadVideoResultRender): JsonObject | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const filtered: JsonObject = {};
    for (const [key, value] of Object.entries(payload)) {
        if (render.consumedKeys.includes(key)) {
            continue;
        }
        if (key === 'audio' && isJsonObject(value)) {
            const audio = filterAudioRecord(value, render.transcriptConsumed);
            if (audio !== null) {
                filtered[key] = audio;
            }
            continue;
        }
        filtered[key] = value;
    }
    return Object.keys(filtered).length > 0 ? filtered : null;
};

export { omitReadVideoResultFields, resolveReadVideoResultRender };
export type { ReadVideoResultRender };
