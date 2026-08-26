/* SoAI - Styled conversation export message rendering [frontend/assets/ts/features/chat/conversationexport/rendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatToolIconServiceContract } from '@core/chat/protocols.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ConversationContract, ConversationMessage } from '@features/chat/ChatTypes.ts';
import { renderConversationExportCompactionBody } from '@features/chat/conversationexport/compactionBoundaryRendering.ts';
import { renderConversationExportMessageMetadata } from '@features/chat/conversationexport/messageMetadata.ts';
import { resolveConversationExportTurns, type ConversationExportComparisonTurn, type ConversationExportMessageTurn } from '@features/chat/conversationexport/turnModel.ts';
import { isContextCompactionBoundaryMessage } from '@features/chat/message/contextcompaction/detection.ts';
import { resolveInlineToolIconHtml } from '@features/chat/message/toolActivityIconHtml.ts';
import { ChatMessageView } from '@features/chat/message/view.ts';
import { buildMessageContentSegments } from '@features/chat/message/messageSegmentsFromContent.ts';
import { resolveRoleClass } from '@features/chat/message/messageview/mappers.ts';
import type { ChatMessage } from '@features/chat/message/messageSegments.ts';
import { resolveRunningActivitySummary } from '@features/chat/toolactivity/runningActivitySummary.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

interface ConversationExportRenderDependencies {
    conversation: ConversationContract;
    sanitizer: SanitizerApi;
    chatToolIconService: ChatToolIconServiceContract;
    getCachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    getMessageSenderLabel(source: ConversationMessage, defaultRole: string): string;
    isThinkingFeatureEnabled(): boolean;
    isRichTextEnabled(): boolean;
    isCodeRecognitionEnabled(): boolean;
    isInlineMultimediaPreviewsEnabled(): boolean;
    isShowActivitiesEnabled(): boolean;
    getAssistantAvatarUrl(): string | null;
    getUserAvatarUrl(): string | null;
    handleError(error: Error, context: string, options?: { notify?: boolean; severity?: 'debug' | 'info' | 'warn' | 'error'; rethrow?: boolean }): void;
}

const createConversationExportMessageView = (dependencies: ConversationExportRenderDependencies): ChatMessageView => {
    return new ChatMessageView({
        sanitizer: dependencies.sanitizer,
        getCanonicalPlan: () => null,
        isConversationExecuting: () => false,
        presentationPreferences: {
            isThinkingFeatureEnabled: () => dependencies.isThinkingFeatureEnabled(),
            isRichTextEnabled: () => dependencies.isRichTextEnabled(),
            isCodeRecognitionEnabled: () => dependencies.isCodeRecognitionEnabled(),
            isInlineMultimediaPreviewsEnabled: () => dependencies.isInlineMultimediaPreviewsEnabled(),
            isShowActivitiesEnabled: () => true,
            getActivityDurationDisplayMode: () => 'all'
        },
        getIcon: (name, options) => dependencies.getCachedIcon(name, options),
        getToolIconHtml: (toolName) => resolveInlineToolIconHtml(dependencies.chatToolIconService, toolName),
        getCurrentConversationId: () => normalizeConversationId(dependencies.conversation.id),
        getCurrentRunningActivitySnapshot: () => null,
        getMessageSenderLabel: (source, defaultRole) => dependencies.getMessageSenderLabel(source, defaultRole),
        resolveMessageContentSegments: (message) => buildMessageContentSegments(message.content),
        resolveRunningActivitySummaryForMarkup: (message, nowMs) => resolveRunningActivitySummary(message, nowMs),
        getPreRenderedAssistantBodyHtml: () => null,
        getLoadingActivityCollapsedState: () => null,
        toggleLoadingActivityCollapsedState: () => false,
        handleError: (error, context, options) => dependencies.handleError(error, context, options),
        avatars: {
            getAssistantAvatarUrl: () => dependencies.getAssistantAvatarUrl(),
            getUserAvatarUrl: () => dependencies.getUserAvatarUrl()
        }
    });
};

const resolveExportTimestampLabel = (dependencies: ConversationExportRenderDependencies, message: ChatMessage): string => {
    const timestamp = message.timestamp;
    if (typeof timestamp !== 'number' || !Number.isFinite(timestamp)) {
        return '';
    }
    return dependencies.sanitizer.html(
        i18n.formatDate(new Date(timestamp), {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        })
    );
};

const resolveExportSenderLabel = (dependencies: ConversationExportRenderDependencies, message: ChatMessage, role: string): string => {
    return dependencies.sanitizer.html(dependencies.getMessageSenderLabel(message, role));
};

const renderMessageForExport = (view: ChatMessageView, dependencies: ConversationExportRenderDependencies, turn: ConversationExportMessageTurn): string => {
    const message = turn.message;
    const role = turn.presentation.normalizedRole;
    const roleClass = resolveRoleClass(role) ?? 'other';
    const sender = resolveExportSenderLabel(dependencies, message, role);
    const timestamp = resolveExportTimestampLabel(dependencies, message);
    const timestampHtml = timestamp ? `<span class="chat-export-message-time">${timestamp}</span>` : '';
    const metadata = renderConversationExportMessageMetadata({ html: (value) => dependencies.sanitizer.html(value) }, message);
    const renderedBody = view.renderMessageTextContent(message, turn.presentation);
    const body = turn.isCompactionBoundary ? renderConversationExportCompactionBody({ html: (value) => dependencies.sanitizer.html(value) }, message, renderedBody) : renderedBody;
    const compactionClass = turn.isCompactionBoundary ? ' chat-export-message--compaction-boundary' : '';
    return `<article class="chat-export-message chat-export-message--${dependencies.sanitizer.attribute(roleClass)}${compactionClass}"><header class="chat-export-message-header"><span class="chat-export-message-role">${sender}</span>${timestampHtml}</header>${metadata}<div class="chat-export-message-body">${body}</div></article>`;
};

const renderComparisonTurnForExport = (view: ChatMessageView, dependencies: ConversationExportRenderDependencies, turn: ConversationExportComparisonTurn): string | null => {
    const entry = turn.entry;
    const title = dependencies.sanitizer.html(i18n.t('chat.export.pdf.comparisonTurn', { count: entry.variantCount }));
    const variants: string[] = [];
    const exportableMessages = new Set(turn.messages);
    for (const variant of entry.variants) {
        if (variant.message !== null && !exportableMessages.has(variant.message)) {
            continue;
        }
        const variantLabel = dependencies.sanitizer.html(i18n.t('chat.export.pdf.variantLabel', { index: variant.variantIndex + 1 }));
        if (variant.message !== null && variant.messageIndex !== null && variant.presentation === null) {
            throw new Error('Chat export comparison message presentation is missing');
        }
        const messageTurn: ConversationExportMessageTurn | null = variant.message && variant.messageIndex !== null && variant.presentation !== null ? { type: 'message', kind: 'assistant', variantCount: 1, messages: [variant.message], previewMessage: variant.message, message: variant.message, presentation: variant.presentation, isCompactionBoundary: isContextCompactionBoundaryMessage(variant.message) } : null;
        const body = messageTurn !== null ? renderMessageForExport(view, dependencies, messageTurn) : `<div class="chat-export-comparison-placeholder">${dependencies.sanitizer.html(i18n.t('chat.export.pdf.emptyVariant'))}</div>`;
        variants.push(`<section class="chat-export-comparison-variant"><div class="chat-export-comparison-variant-label">${variantLabel}</div>${body}</section>`);
    }
    if (variants.length === 0) {
        return null;
    }
    return `<section class="chat-export-comparison-turn" data-assistant-turn-ts="${dependencies.sanitizer.attribute(String(entry.assistantTurnTimestamp))}"><header>${title}</header>${variants.join('')}</section>`;
};

const renderConversationExportMessages = (dependencies: ConversationExportRenderDependencies): string => {
    const view = createConversationExportMessageView(dependencies);
    const turns = resolveConversationExportTurns(dependencies.conversation);
    const rendered: string[] = [];
    for (const turn of turns) {
        if (turn.type === 'message') {
            rendered.push(renderMessageForExport(view, dependencies, turn));
        } else {
            const renderedComparisonTurn = renderComparisonTurnForExport(view, dependencies, turn);
            if (renderedComparisonTurn !== null) {
                rendered.push(renderedComparisonTurn);
            }
        }
    }
    return rendered.join('');
};

export { renderConversationExportMessages };
export type { ConversationExportRenderDependencies };
