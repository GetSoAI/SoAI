/* SoAI - DOM-free rendering logic executed inside a WebWorker [frontend/assets/ts/features/chat/messagerenderworker/renderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import { i18n } from '@core/i18n/index.ts';
import type { SanitizerApi, SanitizerInput } from '@core/pagecontext/public.ts';
import { RichTextRenderer } from '@core/richtextrenderer/service.ts';
import { escapeAttribute, escapeHtml, sanitizeText } from '@core/security/textSanitizer.ts';
import { sanitizeAbsoluteHttpUrl, sanitizeImageSource, sanitizeUrl } from '@core/security/urlSanitizer.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { resolveLoadingActivityErrorText } from '@features/chat/assistanteventtimeline/loadingActivityErrorText.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { buildIconKey, type RenderAssistantBodyFromMessageInput, type RenderInlineDetailsFromMessageInput, type WorkerResources } from '@features/chat/messagerenderworker/protocol.ts';
import { findInlineActivitySegment } from '@features/chat/message/inlineActivitySegmentLookup.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { resolveMessageContentSegmentsForRendering } from '@features/chat/message/messageSegmentsResolution.ts';
import { isThinkingRenderSegment } from '@features/chat/message/messageSegmentTypes.ts';
import { renderAssistantActivityWidgets } from '@features/chat/message/messageview/assistantActivityWidgets.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';
import { renderInlineActivityDetails, renderTimelineMarkup } from '@features/chat/message/messageview/effects.ts';
import { renderMessageError } from '@features/chat/message/messageview/renderCallDetails.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';

type AssistantBodyRenderArguments = Omit<RenderAssistantBodyFromMessageInput, 'context' | 'signal'> & { timelineIndexState: AssistantTimelineIndexState };
type InlineDetailsRenderArguments = Omit<RenderInlineDetailsFromMessageInput, 'context' | 'signal'> & { timelineIndexState: AssistantTimelineIndexState };

const resolveRenderableSegments = (inputArguments: { message: ChatMessage; timelineIndexState: AssistantTimelineIndexState; isThinkingFeatureEnabled: boolean; nowMs: number }): MessageSegment[] => {
    const segments = resolveMessageContentSegmentsForRendering(inputArguments.message, { cancelledPlaceholderText: i18n.t('chat.notifications.requestCancelled'), nowMs: inputArguments.nowMs, timelineIndexState: inputArguments.timelineIndexState });
    if (inputArguments.isThinkingFeatureEnabled) {
        return segments;
    }
    return segments.filter((segment) => Boolean(segment && !isThinkingRenderSegment(segment)));
};

class ChatMessageWorkerRenderer {
    readonly #resources: WorkerResources;
    readonly #richTextRendererWithCodeRecognition: RichTextRenderer;
    readonly #richTextRendererWithoutCodeRecognition: RichTextRenderer;

    constructor(resources: WorkerResources) {
        this.#resources = resources;
        const sanitizer: SanitizerApi = Object.freeze({
            text: (value: SanitizerInput, options?: { allowEmpty?: boolean }): string => {
                const allowEmpty = options?.allowEmpty === true;
                const sanitized = sanitizeText(value ?? '', { trim: true });
                if (!sanitized && !allowEmpty) {
                    return '';
                }
                return sanitized;
            },
            optionalText: (value: SanitizerInput, options?: { allowEmpty?: boolean }): string | null => {
                const sanitized = sanitizeText(value ?? '', { trim: true });
                if (!sanitized && options?.allowEmpty !== true) {
                    return null;
                }
                return sanitized || null;
            },
            html: (value?: SanitizerInput): string => escapeHtml(value ?? ''),
            attribute: (value?: SanitizerInput): string => escapeAttribute(value ?? ''),
            url: (value: SanitizerInput): string | null => sanitizeUrl(value, { allowDataImage: false, allowBlob: true, allowRelative: true }),
            absoluteHttpUrl: (value: SanitizerInput): string | null => sanitizeAbsoluteHttpUrl(value),
            image: (value: SanitizerInput): string | null => sanitizeImageSource(value),
            className: (value: SanitizerInput, defaultClassName?: string, options?: { allowEmpty?: boolean }): string => {
                const allowEmpty = options?.allowEmpty === true;
                const raw = typeof value === 'string' ? value : String(value ?? '');
                const sanitized = sanitizeText(raw, { trim: true });
                if (!sanitized) {
                    return allowEmpty ? '' : (defaultClassName ?? '');
                }
                return sanitized;
            }
        });
        this.#richTextRendererWithCodeRecognition = new RichTextRenderer({ sanitizer, translateFootnoteBackRef: () => i18n.t('richText.footnotes.backToReference'), isCodeRecognitionEnabled: () => true });
        this.#richTextRendererWithoutCodeRecognition = new RichTextRenderer({ sanitizer, translateFootnoteBackRef: () => i18n.t('richText.footnotes.backToReference'), isCodeRecognitionEnabled: () => false });
    }

    #createRenderHost(inputArguments: { isRichTextEnabled: boolean; codeRecognitionEnabled: boolean; isShowActivitiesEnabled: boolean; activityDurationDisplayMode: ChatActivityDurationDisplayMode; isCurrentConversationExecuting: boolean; canonicalPlan: AgentCanonicalPlan | null; nowMs: number }): ChatMessageRenderHost {
        const richTextRenderer = inputArguments.codeRecognitionEnabled ? this.#richTextRendererWithCodeRecognition : this.#richTextRendererWithoutCodeRecognition;
        return {
            nowMs: () => inputArguments.nowMs,
            getCanonicalPlan: () => inputArguments.canonicalPlan,
            escapeHtml: (unsafe: string) => escapeHtml(unsafe),
            escapeAttribute: (value: string) => escapeAttribute(value),
            sanitizeImage: (value: string) => sanitizeImageSource(value),
            getIconHtml: (name: IconName, options?: IconOptions): string => {
                const key = buildIconKey(name, options);
                const html = this.#resources.iconsByKey[key];
                if (typeof html !== 'string' || !html.trim()) {
                    throw new Error(`Chat render worker missing icon: ${key}`);
                }
                return html;
            },
            getToolIconHtml: (): string | null => null,
            isRichTextEnabled: () => inputArguments.isRichTextEnabled,
            isInlineMultimediaPreviewsEnabled: () => false,
            isShowActivitiesEnabled: () => inputArguments.isShowActivitiesEnabled,
            getActivityDurationDisplayMode: () => inputArguments.activityDurationDisplayMode,
            isCurrentConversationExecuting: () => inputArguments.isCurrentConversationExecuting,
            renderRichText: (content: string, wrapCodeBlock, options = {}): string => {
                return richTextRenderer.render(content, { ...options, wrapCodeBlock });
            }
        };
    }

    renderInlineDetailsFromMessageHtml(inputArguments: InlineDetailsRenderArguments): string {
        const host = this.#createRenderHost(inputArguments);
        const segments = resolveRenderableSegments(inputArguments);
        const match = findInlineActivitySegment(segments, inputArguments.expectedType, inputArguments.callId, inputArguments.timelineSequenceIndex);
        if (match) {
            return renderInlineActivityDetails(host, match);
        }
        throw new Error(`Inline activity details segment not found for ${inputArguments.expectedType}:${inputArguments.callId}.`);
    }

    renderAssistantBodyFromMessageHtml(inputArguments: AssistantBodyRenderArguments): string {
        const host = this.#createRenderHost(inputArguments);
        const segments = resolveRenderableSegments(inputArguments);
        const contentHtml = renderTimelineMarkup(host, segments, { sortableTextTables: true });
        const errorText = resolveLoadingActivityErrorText(inputArguments.message);
        const widgetsHtml = inputArguments.suppressAssistantActivityWidgets ? '' : renderAssistantActivityWidgets(host, segments);
        const errorHtml = errorText ? renderMessageError(host, errorText) : '';
        return `${contentHtml}${widgetsHtml}${errorHtml}`;
    }
}

export { ChatMessageWorkerRenderer };
