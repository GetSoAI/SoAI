/* SoAI - Assistant generated image activity card [frontend/assets/ts/features/chat/message/messageview/assistantGeneratedImageWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { renderChatMultimediaPreviewActionAttributes, resolveChatMultimediaPreviewSourceReferenceForUrl } from '@features/chat/message/multimediaPreviewDataset.ts';
import { renderAssistantActivityWidgetFooter } from '@features/chat/message/messageview/assistantActivityWidgetFooter.ts';
import { shouldRenderActivityDuration } from '@features/chat/message/messageview/activityDurationDisplay.ts';
import { resolveInlineToolActivityDurationLabel } from '@features/chat/message/messageview/inlineToolDurationLabel.ts';
import { renderToolOutputAction } from '@features/chat/message/messageview/toolOutputAction.ts';
import type { ChatMessageRenderHost, MessageSegment } from '@features/chat/message/messageview/types.ts';
import { resolveGeneratedImagePresentation } from '@features/chat/toolactivity/generatedImagePresentation.ts';
import { buildInlineImageDataUrl, resolveImageDownloadName } from '@features/chat/toolactivity/toolImagePayload.ts';

const IMAGE_WIDGET_ICON_OPTIONS = Object.freeze({ size: 16, strokeWidth: 1.5 });

const renderAssistantGeneratedImageWidget = (host: ChatMessageRenderHost, segment: MessageSegment): string => {
    if (segment.type !== 'inline_tool_activity') return '';
    const model = resolveGeneratedImagePresentation(segment);
    if (model === null) return '';
    const title = i18n.t('chat.message.generatedImage');
    const sanitizedSource = model.payload === null ? null : host.sanitizeImage(buildInlineImageDataUrl(model.payload.contentType, model.payload.imageBase64));
    const displayState = model.state === 'completed' && sanitizedSource === null ? 'unavailable' : model.state;
    const stateLabel = displayState === 'pending' ? i18n.t('chat.activityWidgets.imageWaiting') : displayState === 'running' ? i18n.t('chat.activityWidgets.imageGenerating') : displayState === 'cancelled' ? i18n.t('chat.notifications.requestCancelled') : displayState === 'error' ? i18n.t('chat.toolActivity.status.error') : displayState === 'unavailable' ? i18n.t('chat.activityWidgets.imageUnavailable') : i18n.t('chat.toolActivity.status.completed');
    const duration = shouldRenderActivityDuration(host.getActivityDurationDisplayMode(), segment.status) ? resolveInlineToolActivityDurationLabel({ ...segment, nowMs: host.nowMs() }) : null;
    const durationHtml = duration === null ? '' : `<span class="assistant-image-widget__duration">${host.escapeHtml(duration)}</span>`;
    const geometry = model.geometry ?? { width: 1, height: 1 };
    let media = '';
    let actions = '';
    if (model.payload !== null) {
        const source = sanitizedSource;
        if (source !== null) {
            const downloadName = resolveImageDownloadName(model.payload.contentType, 'soai-generated-image.png');
            const openAction: InlineMediaOpenAction = { type: 'image', previewUrl: source, openSourceUrl: source, title, downloadName, downloadUrl: null, contentType: model.payload.contentType, contentLength: model.payload.contentLength, sourceReference: resolveChatMultimediaPreviewSourceReferenceForUrl(source), requireMetadata: false };
            const attributes = renderChatMultimediaPreviewActionAttributes(openAction);
            const downloadAttributes = renderChatMultimediaPreviewActionAttributes(openAction, 'download');
            media = `<img class="assistant-image-widget__backdrop" src="${host.escapeAttribute(source)}" alt="" aria-hidden="true" loading="lazy" decoding="async"><button type="button" class="assistant-image-widget__preview" aria-label="${host.escapeAttribute(title)}" data-tooltip="${host.escapeAttribute(title)}"${attributes.html}><img class="assistant-image-widget__image" src="${host.escapeAttribute(source)}" alt="${host.escapeAttribute(title)}" loading="lazy" decoding="async"></button>`;
            const downloadLabel = i18n.t('fileExplorer.modal.download');
            actions = `<a class="ui-button ui-button--sm ui-variant-neutral" href="#" download="${host.escapeAttribute(downloadName)}"${downloadAttributes.html} aria-label="${host.escapeAttribute(downloadLabel)}">${host.getIconHtml('download', IMAGE_WIDGET_ICON_OPTIONS)}${host.escapeHtml(downloadLabel)}</a>`;
        }
    }
    const status = model.state === 'error' ? `${model.error || stateLabel} ${i18n.t('chat.activityWidgets.imageRetry')}` : stateLabel;
    const placeholder = media ? '' : `<div class="assistant-image-widget__placeholder">${host.getIconHtml('file-image', IMAGE_WIDGET_ICON_OPTIONS)}<p role="status">${host.escapeHtml(status)}</p></div>`;
    const startedAt = segment.startedAtMs === undefined ? '' : ` data-started-at-ms="${host.escapeAttribute(String(segment.startedAtMs))}"`;
    const settledDuration = segment.durationMs === undefined || segment.status === 'running' || segment.status === 'pending' ? '' : ` data-settled-duration-ms="${host.escapeAttribute(String(segment.durationMs))}"`;
    const fullOutput = model.state === 'unavailable' ? renderToolOutputAction(host, segment) : '';
    return `<section class="assistant-image-widget" data-image-widget-status="${host.escapeAttribute(segment.status)}"${startedAt}${settledDuration}><header class="assistant-image-widget__header"><span class="assistant-image-widget__title">${host.getIconHtml('file-image', IMAGE_WIDGET_ICON_OPTIONS)}${host.escapeHtml(title)}</span><span class="assistant-image-widget__timing">${durationHtml}</span></header>${model.prompt ? `<p class="assistant-image-widget__prompt" dir="auto">${host.escapeHtml(model.prompt)}</p>` : ''}<div class="assistant-image-widget__stage" style="--assistant-image-aspect:${host.escapeAttribute(`${String(geometry.width)} / ${String(geometry.height)}`)};--assistant-image-ratio:${host.escapeAttribute(String(geometry.width / geometry.height))}">${media}${placeholder}${media ? `<p class="assistant-image-widget__load-error" role="status">${host.escapeHtml(i18n.t('chat.activityWidgets.imageUnavailable'))}</p>` : ''}</div>${actions || fullOutput ? `<div class="assistant-image-widget__actions">${actions}${fullOutput}</div>` : ''}${renderAssistantActivityWidgetFooter(host, segment.startedAtMs)}</section>`;
};

export { IMAGE_WIDGET_ICON_OPTIONS, renderAssistantGeneratedImageWidget };
