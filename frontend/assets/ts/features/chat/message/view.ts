/* SoAI - Chat feature message rendering [frontend/assets/ts/features/chat/message/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatMessageTimestamp, renderMessageActions } from '@features/chat/message/messageActionMarkup.ts';
import { type MessageSegment, type ChatMessage } from '@features/chat/message/messageSegments.ts';
import { CHAT_ICON_SIZE_XS } from '@features/chat/chatConstants.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { isThinkingRenderSegment } from '@features/chat/message/messageSegmentTypes.ts';
import { renderMessageError } from '@features/chat/message/messageview/renderCallDetails.ts';
import { renderMarkdownContent } from '@features/chat/message/messageview/renderMarkdown.ts';
import { resolveShouldCacheSettledAssistantBody } from '@features/chat/message/messageview/assistantBodyCachePolicy.ts';
import { renderSegments, renderTimelineMarkup } from '@features/chat/message/messageview/effects.ts';
import { renderAssistantActivityWidgets } from '@features/chat/message/messageview/assistantActivityWidgets.ts';
import { createRenderFailurePresenter } from '@features/chat/message/messageview/renderFailurePresentation.ts';
import { createMainThreadChatMessageRenderHost } from '@features/chat/message/messageview/renderHost.ts';
import { renderInlineLoadingActivityGroup } from '@features/chat/message/messageview/renderInlineLoadingActivityGroup.ts';
import { resolveMessageDomId, resolveRoleClass } from '@features/chat/message/messageview/mappers.ts';
import { renderMessageHeaderRoleMarkup } from '@features/chat/message/messageview/renderMessageHeaderRoleMarkup.ts';
import { renderMessageTextContent } from '@features/chat/message/messageview/renderMessageTextContent.ts';
import type { ChatMessageRenderHost, MessageRenderOptions, RenderedMessageTextContent } from '@features/chat/message/messageview/types.ts';
import { isAssistantMessageRole } from '@features/chat/message/messageRole.ts';
import { renderChatMessageAvatarContainer } from '@features/chat/message/chatMessageAvatarMarkup.ts';
import { buildMessageContentSegments } from '@features/chat/message/messageSegmentsFromContent.ts';
import { resolveContextCompactionBoundaryRenderModel } from '@features/chat/message/contextcompaction/renderModel.ts';
import { flattenTextFragments } from '@features/chat/message/messageTextFlattening.ts';
import type { ChatMessageRenderModel } from '@features/chat/message/messageRenderModel.ts';
import { resolveAssistantSemanticIdentityKey } from '@features/chat/message/assistantMessageIdentity.ts';
import type { ChatMessageViewDependencies } from '@features/chat/message/messageViewContracts.ts';
import { injectAssistantBodyRootAttributes } from '@features/chat/message/assistantBodyRootAttributes.ts';
import { buildAssistantResponseMarkup } from '@features/chat/message/assistantResponseMarkup.ts';
import { renderChatPostRenderCapabilitiesAttribute } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';

class ChatMessageView {
    readonly #dependencies: ChatMessageViewDependencies;
    readonly #renderHost: ChatMessageRenderHost;
    readonly #renderFailurePresenter: ReturnType<typeof createRenderFailurePresenter>;

    constructor(dependencies: ChatMessageViewDependencies) {
        this.#dependencies = dependencies;
        this.#renderHost = createMainThreadChatMessageRenderHost({
            sanitizer: this.#dependencies.sanitizer,
            getCanonicalPlan: () => this.#dependencies.getCanonicalPlan(),
            getIcon: (name, options) => this.#dependencies.getIcon(name, options),
            getToolIconHtml: (toolName) => this.#dependencies.getToolIconHtml(toolName),
            isRichTextEnabled: () => this.#dependencies.presentationPreferences.isRichTextEnabled(),
            isCodeRecognitionEnabled: () => this.#dependencies.presentationPreferences.isCodeRecognitionEnabled(),
            isInlineMultimediaPreviewsEnabled: () => this.#dependencies.presentationPreferences.isInlineMultimediaPreviewsEnabled(),
            isShowActivitiesEnabled: () => this.#dependencies.presentationPreferences.isShowActivitiesEnabled(),
            getActivityDurationDisplayMode: () => this.#dependencies.presentationPreferences.getActivityDurationDisplayMode(),
            isCurrentConversationExecuting: () => {
                const conversationId = this.#dependencies.getCurrentConversationId();
                return conversationId !== null && this.#dependencies.isConversationExecuting(conversationId);
            }
        });
        this.#renderFailurePresenter = createRenderFailurePresenter({
            renderHost: this.#renderHost,
            handleError: (error, context, options) => this.#dependencies.handleError(error, context, options),
            renderPreservedContentOnlyMarkup: (message) => this.#renderPreservedContentOnlyMarkup(message),
            renderPreservedPlainTextMarkup: (message) => this.#renderPreservedPlainTextMarkup(message)
        });
    }

    escapeHtml(unsafe: string): string {
        return this.#dependencies.sanitizer.html(unsafe);
    }

    #isAssistantRole(message: ChatMessage): boolean {
        return isAssistantMessageRole(message);
    }

    #resolveSenderLabel(message: ChatMessage, role: string): string {
        return this.#dependencies.getMessageSenderLabel(message, role);
    }

    escapeAttribute(value: string): string {
        return this.#dependencies.sanitizer.attribute(value);
    }

    #renderPreservedContentOnlyMarkup(message: ChatMessage): string {
        const hideDefaultImageLabel = !this.#isAssistantRole(message);
        const segments = buildMessageContentSegments(message.content);
        if (this.#isAssistantRole(message)) {
            return this.#renderTimelineSegmentsMarkup(segments);
        }
        return this.#renderSegmentsWithOptions(segments, { hideDefaultImageLabel, compactAttachmentCards: true, conversationId: this.#dependencies.getCurrentConversationId() });
    }

    #renderPreservedPlainTextMarkup(message: ChatMessage): string {
        const fragments = flattenTextFragments(message.content);
        const text = fragments.length > 0 ? fragments.join('') : '';
        const escaped = this.escapeHtml(text);
        const markup = `<p>${escaped.replace(/\n/g, '<br>')}</p>`;
        return this.#isAssistantRole(message) ? injectAssistantBodyRootAttributes(this.#renderHost, markup, 'render_failure_text:1', text) : markup;
    }

    shouldCacheSettledAssistantBody(message: ChatMessage): boolean {
        return resolveShouldCacheSettledAssistantBody({
            message,
            isShowActivitiesEnabled: this.#dependencies.presentationPreferences.isShowActivitiesEnabled(),
            collapsedState: this.#dependencies.getLoadingActivityCollapsedState(message)
        });
    }

    #renderMessageTextContent(message: ChatMessage, presentation: ChatMessageRenderModel['presentation'], segments: MessageSegment[] | null, forceSettledAssistantBody: boolean, conversationId: string | null = this.#dependencies.getCurrentConversationId()): RenderedMessageTextContent {
        return renderMessageTextContent(
            {
                nowMs: this.#renderHost.nowMs,
                isShowActivitiesEnabled: () => this.#dependencies.presentationPreferences.isShowActivitiesEnabled(),
                getCurrentConversationId: () => conversationId,
                resolveMessageContentSegments: (candidateMessage) => this.#dependencies.resolveMessageContentSegments(candidateMessage),
                getPreRenderedAssistantBodyHtml: (candidateMessage) => this.#dependencies.getPreRenderedAssistantBodyHtml(candidateMessage),
                getLoadingActivityCollapsedState: (candidateMessage) => this.#dependencies.getLoadingActivityCollapsedState(candidateMessage),
                renderSegmentsWithOptions: (renderSegments, options) => this.#renderSegmentsWithOptions(renderSegments, options),
                renderTimelineSegmentsMarkup: (renderSegments) => this.#renderTimelineSegmentsMarkup(renderSegments),
                renderAssistantBodyItem: (markup, key, signature) => injectAssistantBodyRootAttributes(this.#renderHost, markup, key, signature),
                renderAssistantActivityWidgets: (renderSegments) => this.renderAssistantActivityWidgets(renderSegments),
                resolveRenderableSegments: (renderSegments) => this.#resolveRenderableSegments(renderSegments),
                renderLoadingActivityGroup: (segment, inputArguments) => renderInlineLoadingActivityGroup(this.#renderHost, { segment, ...inputArguments }),
                renderMessageErrorMarkup: (errorText) => renderMessageError(this.#renderHost, errorText),
                handleMessageRenderError: (candidateMessage, error, context) => this.#renderFailurePresenter.renderWithPreservedContent(candidateMessage, error, context)
            },
            message,
            presentation,
            segments,
            forceSettledAssistantBody ? { forceSettledAssistantBody: true } : {}
        );
    }

    renderMessageTextContent(message: ChatMessage, presentation: ChatMessageRenderModel['presentation'], segments: MessageSegment[] | null = null): string {
        return this.#renderMessageTextContent(message, presentation, segments, false).html;
    }

    renderActiveStreamMessageTextContent(message: ChatMessage, presentation: ChatMessageRenderModel['presentation']): RenderedMessageTextContent {
        return this.#renderMessageTextContent(message, presentation, null, false);
    }

    renderMessage(model: ChatMessageRenderModel, getModelTypeLabel: (modelId: string | null) => string | null): TrustedHtml {
        const message = model.message;
        const conversationId = model.conversationId;
        const index = model.index;
        const role = model.presentation.normalizedRole;

        if (!isNumber(message.timestamp)) {
            throw new Error('Chat message is missing timestamp');
        }
        const messageTimestamp = message.timestamp;
        const timestamp = formatMessageTimestamp(messageTimestamp);
        const messageDomId = resolveMessageDomId(message, index);
        const senderLabel = this.#resolveSenderLabel(message, role);
        const messageModelId = isString(message.modelId) && message.modelId.trim() ? message.modelId.trim() : null;
        const modelTypeLabel = role === 'assistant' ? getModelTypeLabel(messageModelId) : null;
        const compactionBoundary = resolveContextCompactionBoundaryRenderModel(message);
        const isCompactionBoundary = compactionBoundary.isBoundary;
        const comparisonTurn = model.comparisonTurn;
        const comparisonRootAttributes = comparisonTurn
            ? (() => {
                  const assistantTurnAttr = this.escapeAttribute(String(comparisonTurn.assistantTurnTimestamp));
                  const variantAttr = this.escapeAttribute(String(comparisonTurn.modelVariantIndex));
                  const totalAttr = this.escapeAttribute(String(comparisonTurn.variantCount));
                  const activeAttr = this.escapeAttribute(String(comparisonTurn.activeVariantIndex));
                  const comparisonState = comparisonTurn.invalidReason === null ? 'valid' : 'invalid';
                  const invalidReason = comparisonTurn.invalidReason;
                  const invalidReasonAttribute = invalidReason === null ? '' : ` data-comparison-turn-error="${this.escapeAttribute(invalidReason)}"`;
                  return ` data-assistant-turn-ts="${assistantTurnAttr}" data-model-variant-index="${variantAttr}" data-comparison-variant-total="${totalAttr}" data-comparison-active-variant-index="${activeAttr}" data-comparison-turn-state="${comparisonState}"${invalidReasonAttribute}`;
              })()
            : '';
        const isInvalidComparisonTurn = comparisonTurn !== null && comparisonTurn.invalidReason !== null;

        const roleClass = resolveRoleClass(role);
        const messageClassSuffix = `${roleClass ? ` ${roleClass}` : ''}${compactionBoundary.rootClassName}`;
        const assistantSemanticIdentityAttributes = message.role === 'assistant' ? ` data-assistant-semantic-id="${this.escapeAttribute(resolveAssistantSemanticIdentityKey(message, 'Chat message render'))}"` : '';
        const avatarContainerHtml = isCompactionBoundary
            ? ''
            : renderChatMessageAvatarContainer(
                  {
                      escapeAttribute: (value) => this.escapeAttribute(value),
                      escapeHtml: (value) => this.escapeHtml(value),
                      getAssistantAvatarUrl: () => this.#dependencies.avatars.getAssistantAvatarUrl(),
                      getUserAvatarUrl: () => this.#dependencies.avatars.getUserAvatarUrl(),
                      getIconHtml: (name, options) => this.#dependencies.getIcon(name, options).html
                  },
                  role,
                  senderLabel
              );

        if (model.presentation.isPendingDeletion) {
            const deletedText = this.escapeHtml(i18n.t('chat.message.deleted'));
            const undoLabel = i18n.t('chat.message.actions.undoDelete');
            const undoLabelHtml = this.escapeHtml(undoLabel);
            const undoLabelAttr = this.escapeAttribute(undoLabel);
            const undoIconHtml = renderIconSlot(this.#dependencies.getIcon('undo', CHAT_ICON_SIZE_XS));
            const deleteNowLabel = i18n.t('chat.message.actions.delete');
            const deleteNowLabelAttr = this.escapeAttribute(deleteNowLabel);
            const deleteNowIconHtml = renderIconSlot(this.#dependencies.getIcon('close', CHAT_ICON_SIZE_XS));
            const deletedMessageMarkup = avatarContainerHtml + `<div class="message-content message-content--deleted glass-surface-strong glass-surface--no-shadow">` + `<div class="message-text">` + `<p><strong class="message-deleted-badge">${deletedText}</strong></p>` + `<p class="message-deleted-actions"><button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="delete-undo" aria-label="${undoLabelAttr}" data-tooltip="${undoLabelAttr}">${undoIconHtml}${undoLabelHtml}</button><button type="button" class="ui-icon-button ui-variant-danger delete-message-now-btn" data-action="delete-now" aria-label="${deleteNowLabelAttr}" data-tooltip="${deleteNowLabelAttr}">${deleteNowIconHtml}</button></p>` + `</div>` + `</div>`;
            return toTrustedUiHtml(`<div class="chat-message${messageClassSuffix}" data-id="${this.escapeAttribute(messageDomId)}"${assistantSemanticIdentityAttributes}${renderChatPostRenderCapabilitiesAttribute('')}>${deletedMessageMarkup}</div>`);
        }

        const textHtml = isInvalidComparisonTurn ? buildAssistantResponseMarkup({ bodyHtml: renderMessageError(this.#renderHost, i18n.t('chat.comparison.invalidTurn')) }) : this.#renderMessageTextContent(message, model.presentation, null, model.forceSettledAssistantBody === true, conversationId).html;
        const actionsHtml = !compactionBoundary.renderActions
            ? ''
            : renderMessageActions(
                  {
                      escapeHtml: (value) => this.escapeHtml(value),
                      escapeAttribute: (value) => this.escapeAttribute(value),
                      getIcon: (name, options) => this.#dependencies.getIcon(name, options).html,
                      isConversationExecuting: (conversationId) => this.#dependencies.isConversationExecuting(conversationId),
                      getCurrentConversationId: () => conversationId,
                      getCurrentRunningActivitySnapshot: () => this.#dependencies.getCurrentRunningActivitySnapshot(),
                      resolveRunningActivitySummaryForMarkup: (candidateMessage, nowMs) => this.#dependencies.resolveRunningActivitySummaryForMarkup(candidateMessage, nowMs)
                  },
                  message,
                  timestamp,
                  model.presentation,
                  isInvalidComparisonTurn ? 'invalid_comparison_turn' : isCompactionBoundary ? 'compaction_boundary' : 'default',
                  { forceSettledAssistantActions: model.forceSettledAssistantActions === true }
              );

        const headerRoleHtml = isCompactionBoundary
            ? ''
            : renderMessageHeaderRoleMarkup(
                  {
                      escapeHtml: (value) => this.escapeHtml(value),
                      escapeAttribute: (value) => this.escapeAttribute(value),
                      getIconHtml: (name, options) => this.#dependencies.getIcon(name, options).html,
                      nowMs: this.#renderHost.nowMs,
                      getActivityDurationDisplayMode: this.#renderHost.getActivityDurationDisplayMode
                  },
                  {
                      role,
                      senderLabel,
                      messageModelId,
                      modelTypeLabel,
                      comparisonTurn,
                      message
                  }
              );
        const contentClassName = `message-content message-content--with-header glass-surface-strong glass-surface--no-shadow${compactionBoundary.contentClassName}`;
        const headerHtml = isCompactionBoundary ? '' : `<div class="message-header"><span class="message-role">${headerRoleHtml}</span></div>`;

        const messageMarkup = avatarContainerHtml + `<div class="${contentClassName}">` + headerHtml + `<div class="message-text">${textHtml}</div>` + `${actionsHtml}` + `</div>`;
        return toTrustedUiHtml(`<div class="chat-message${messageClassSuffix}" data-id="${this.escapeAttribute(messageDomId)}"${assistantSemanticIdentityAttributes}${comparisonRootAttributes}${renderChatPostRenderCapabilitiesAttribute(textHtml)}>${messageMarkup}</div>`);
    }

    #resolveRenderableSegments(segments: MessageSegment[]): MessageSegment[] {
        return this.#dependencies.presentationPreferences.isThinkingFeatureEnabled() ? segments : segments.filter((segment) => Boolean(segment && !isThinkingRenderSegment(segment)));
    }

    #renderSegmentsWithOptions(segments: MessageSegment[], options: MessageRenderOptions = {}): string {
        return renderSegments(this.#renderHost, this.#resolveRenderableSegments(segments), options);
    }

    #renderTimelineSegmentsMarkup(segments: MessageSegment[]): string {
        return renderTimelineMarkup(this.#renderHost, this.#resolveRenderableSegments(segments), { sortableTextTables: true });
    }

    renderSegments(segments: MessageSegment[], options: MessageRenderOptions = {}): string {
        return this.#renderSegmentsWithOptions(segments, options);
    }

    renderAssistantActivityWidgets(segments: readonly MessageSegment[]): string {
        return renderAssistantActivityWidgets(this.#renderHost, segments);
    }

    renderMarkdownContent(content: string, options: { sortableTables?: boolean } = {}): string {
        return renderMarkdownContent(this.#renderHost, content, options);
    }

    renderStreamingMarkdownContent(content: string): string {
        return renderMarkdownContent(this.#renderHost, content, { tableMode: 'streaming' });
    }

    renderMessageErrorHtml(errorText: string): string {
        return renderMessageError(this.#renderHost, errorText);
    }
}

export { ChatMessageView };
