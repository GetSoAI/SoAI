/* SoAI - Chat stream start orchestration [frontend/assets/ts/features/chat/chatstreamservice/controller/actions/streamResponse.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { markContentPreviewFeedbackDelivered } from '@features/chat/contentPreviewFeedbackState.ts';
import { clearStreamingContext, isConversationStreamingUiActive, requireConversationStreamState } from '@features/chat/chatstreamservice/controller/state.ts';
import { resolveConversationTitle, resolveModelId } from '@features/chat/chatstreamservice/controller/effects.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { requireChatExecutionModelPreflight } from '@features/chat/modelExecutionPreflight.ts';
import type { ChatStreamingControllerContext, ChatStreamResponseOptions } from '@features/chat/chatstreamservice/controller/types.ts';
import { beginRequestToken, buildRequestId, isActiveRequest } from '@features/chat/chatstreamservice/controller/actions/requestTracking.ts';
import { buildComparisonVariantRequestId } from '@features/chat/chatstreamservice/comparisonRequestIdentity.ts';
import { waitForRequestTerminalization } from '@features/chat/chatstreamservice/controller/terminalLifecycle.ts';
import { waitForTerminalReconciliation } from '@features/chat/chatstreamservice/controller/terminalizationState.ts';
import { resolveContentPreviewFeedbackForStreamStart, resolvePreviewContractFeedbackForStreamStart } from '@features/chat/chatstreamservice/controller/streamStartPreparation.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';
import { abortPendingStreamStartLifecycle, beginComparisonVariantLifecycle, beginStreamStartLifecycle, markComparisonRunAborting, settleNonCompleteStreamStartOutcome } from '@features/chat/chatstreamservice/controller/streamLifecycle.ts';
import { ChatStreamTerminalizationError, reportChatStreamTerminalizationFailureOnce } from '@features/chat/chatstreamservice/controller/terminalizationError.ts';
import { serializeConversationMcpSettings } from '@core/chat/executionSettingsMapping.ts';

export async function streamResponse(context: ChatStreamingControllerContext, conversation: ConversationContract, options: ChatStreamResponseOptions = {}): Promise<void> {
    if (context.disposed) {
        throw new Error('Chat streaming controller is disposed');
    }
    if (!conversation || !isObject(conversation)) {
        throw new Error('Chat stream requires a conversation object');
    }

    const conversationRecord = conversation;
    const conversationId = requireConversationId(conversationRecord['id'], 'Conversation');
    throwIfAborted(options.abortSignal, 'Chat stream start aborted');
    await waitForTerminalReconciliation(context, conversationId, options.abortSignal ?? null);
    throwIfAborted(options.abortSignal, 'Chat stream start aborted');
    if (isConversationStreamingUiActive(context, conversationId)) {
        throw new Error('Cannot start chat stream while this conversation is already streaming');
    }

    const selectedModelId = resolveModelId(context);
    const modelPreflight =
        options.executionModelPlan ??
        requireChatExecutionModelPreflight({
            conversation: conversationRecord,
            selectedModelId,
            modelStreamHasPayload: context.dependencies.getModelStreamHasPayload(),
            isModelAvailable: (modelId) => context.dependencies.isModelAvailable(modelId)
        });
    const resolvedModelId = modelPreflight.primaryModelId;
    const comparisonModels = modelPreflight.comparisonModelIds;

    const requestToken = beginRequestToken(context, conversationId);
    const groupRequestId = buildRequestId(conversationId, requestToken);
    const streamState = requireConversationStreamState(context, conversationId);
    const resolvedContentPreviewFeedback = resolveContentPreviewFeedbackForStreamStart(conversation, options);
    const contentPreviewFeedback = resolvedContentPreviewFeedback.contentPreviewFeedback;
    const contentPreviewFeedbackMessage = resolvedContentPreviewFeedback.contentPreviewFeedbackSourceMessage;
    const previewContractFeedback = resolvePreviewContractFeedbackForStreamStart(conversation.messages[conversation.messages.length - 1] ?? null, options);
    beginStreamStartLifecycle(context, { conversationId, groupRequestId, state: streamState });

    const abortPendingStart = (note: string): void => {
        abortPendingStreamStartLifecycle(context, conversationId, note);
    };

    try {
        if (options.skipInitialMessageSync !== true) {
            await context.dependencies.storageManager.saveAndSync(conversationRecord, { messageSyncMode: 'append_tail' });
            throwIfAborted(options.abortSignal, 'Chat stream start aborted');
            try {
                options.onInitialSyncComplete?.();
            } catch (error) {
                if (options.reportRequestFailure !== false) {
                    context.dependencies.reportRequestFailure(ensureError(error));
                }
            }
        }
        if (!isActiveRequest(context, conversationId, requestToken)) {
            abortPendingStart('stream superseded before start');
            throw new Error('Chat stream request was superseded before start');
        }

        const requestParameters = context.dependencies.getRequestParameters();
        const conversationModelSettings = conversationRecord.modelSettings;
        const mcpSettings = conversationModelSettings?.mcp;
        const preflightArguments = {
            conversationId,
            primaryModelId: resolvedModelId,
            comparisonModelIds: comparisonModels,
            ...(options.minimumAssistantTurnAtMs === undefined ? {} : { minimumAssistantTurnAtMs: options.minimumAssistantTurnAtMs })
        };
        const preflight = await context.dependencies.preflightComparisonTurn(preflightArguments);
        throwIfAborted(options.abortSignal, 'Chat stream start aborted');
        if (!isActiveRequest(context, conversationId, requestToken)) {
            abortPendingStart('stream superseded during comparison preflight');
            return;
        }
        streamState.comparisonRun =
            preflight.variants.length > 1
                ? {
                      groupRequestId,
                      assistantTurnTimestamp: preflight.assistantTurnTimestamp,
                      variantCount: preflight.variants.length,
                      aborting: false
                  }
                : null;

        for (let variantIndex = 0; variantIndex < preflight.variants.length; variantIndex += 1) {
            if (!isActiveRequest(context, conversationId, requestToken)) {
                abortPendingStart('stream superseded during comparison');
                return;
            }
            const variant = preflight.variants[variantIndex] ?? null;
            if (!variant) {
                throw new Error('Comparison preflight variants are missing required entries');
            }
            const modelForVariant = variant.requestedModelId;
            const variantTimestamp = variant.assistantTimestamp;
            const variantRequestId = preflight.variants.length > 1 ? buildComparisonVariantRequestId(groupRequestId, variantIndex) : groupRequestId;
            beginComparisonVariantLifecycle(context, { conversationId, state: streamState, requestId: variantRequestId, assistantTimestamp: variantTimestamp });
            if (!isActiveRequest(context, conversationId, requestToken)) {
                abortPendingStart('stream superseded after variant lifecycle start');
                return;
            }
            const assistantTurnTimestamp = preflight.assistantTurnTimestamp;
            if (!isJsonObject(requestParameters)) {
                throw new Error('Chat stream request parameters must be JSON');
            }
            const requestBody: JsonObject = {
                model: modelForVariant,
                ...requestParameters
            };
            if (mcpSettings !== undefined) {
                requestBody['mcp'] = serializeConversationMcpSettings(mcpSettings);
            }
            const onFirstServerEvent =
                variantIndex === 0
                    ? async (): Promise<void> => {
                          if (contentPreviewFeedbackMessage !== null) {
                              markContentPreviewFeedbackDelivered(contentPreviewFeedbackMessage);
                          }
                          if (options.onFirstServerEvent) {
                              await options.onFirstServerEvent();
                          }
                      }
                    : null;
            if (context.dependencies.chatStreamService.isStreaming(conversationId)) {
                throw new Error('Cannot start chat stream while this conversation is already streaming');
            }
            if (!isActiveRequest(context, conversationId, requestToken)) {
                abortPendingStart('stream superseded before service start');
                return;
            }
            if (variantIndex === 0 && options.beforeFirstVariantStart) {
                await options.beforeFirstVariantStart();
                throwIfAborted(options.abortSignal, 'Chat stream start aborted');
                if (!isActiveRequest(context, conversationId, requestToken)) {
                    abortPendingStart('stream superseded before first variant start');
                    return;
                }
            }
            const conversationTitle = resolveConversationTitle(conversation);
            const status = await context.dependencies.chatStreamService.start({
                conversationId,
                conversationTitle,
                model: modelForVariant,
                assistantTimestamp: variantTimestamp,
                assistantTurnTimestamp,
                modelVariantIndex: variantIndex,
                requestBody,
                requestId: variantRequestId,
                abortSignal: options.abortSignal ?? null,
                contentPreviewFeedback,
                previewContractFeedback,
                ...(variantIndex === 0 ? { onFirstServerEvent } : {})
            });
            if (status === 'detached') {
                clearStreamingContext(context, conversationId);
                return;
            }
            if (!isActiveRequest(context, conversationId, requestToken)) {
                return;
            }
            throwIfAborted(options.abortSignal, 'Chat stream start aborted');
            if (variantIndex < preflight.variants.length - 1) {
                if (context.dependencies.state.getCurrentConversationId() === conversationId) {
                    await waitForRequestTerminalization(context, { conversationId, requestId: variantRequestId, assistantTimestamp: variantTimestamp });
                }
                throwIfAborted(options.abortSignal, 'Chat stream start aborted');
                if (!isActiveRequest(context, conversationId, requestToken)) {
                    return;
                }
            }
            if (status !== 'complete') {
                markComparisonRunAborting(streamState);
                await settleNonCompleteStreamStartOutcome(context, {
                    conversationId,
                    requestToken,
                    requestId: variantRequestId,
                    assistantTimestamp: variantTimestamp,
                    signal: options.abortSignal ?? null
                });
                return;
            }
        }
        if (context.dependencies.state.getCurrentConversationId() !== conversationId) {
            clearStreamingContext(context, conversationId);
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isActiveRequest(context, conversationId, requestToken)) {
            return;
        }

        if (isAbortError(runtimeError)) {
            markComparisonRunAborting(streamState);
            abortPendingStart('stream start aborted');
            throw runtimeError;
        }
        if (runtimeError instanceof ChatStreamTerminalizationError) {
            markComparisonRunAborting(streamState);
            if (options.reportRequestFailure !== false) {
                reportChatStreamTerminalizationFailureOnce(runtimeError, (failure) => context.dependencies.reportRequestFailure(failure));
            }
            throw runtimeError;
        }
        markComparisonRunAborting(streamState);
        abortPendingStart('stream start failure');
        if (options.reportRequestFailure !== false) {
            context.dependencies.reportRequestFailure(runtimeError);
        }
        throw runtimeError;
    }
}
