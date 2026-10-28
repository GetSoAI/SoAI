/* SoAI - Central assistant render transaction and render-signature commit [frontend/assets/ts/features/chat/message/assistantRenderTransaction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cancelLoadingActivityTransition } from '@features/chat/message/loadingActivityToggleRegistry.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import { collectAssistantDomState, type AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { applyParsedAssistantMessageRoot, applyRenderedAssistantMessageRoot } from '@features/chat/message/assistantMessageMarkupPatching.ts';
import { commitAssistantRenderCacheUpdate, type AssistantRenderCacheUpdate } from '@features/chat/message/assistantRenderCacheUpdate.ts';
import { hasStreamingAssistantDom, normalizeSettledAssistantDom } from '@features/chat/message/assistantSettledDom.ts';
import { withAssistantViewportStability, type AssistantViewportStabilityScope } from '@features/chat/message/assistantViewportStability.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import { animatePresenceMorph, deferUntilPresenceExitsSettle, isPresenceMorphing, measurePresenceSize, prepareEnterWithPresence, stopPresenceAnimation } from '@core/animations/presence/public.ts';
import { optionalClosestElement } from '@core/dom/attributes.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { isMainTimelineAutoScrollLocked } from '@features/chat/mainTimelineScroll.ts';
import { isSpinnerStatusTerminalTransitionActive } from '@features/chat/stream/streamMessageSpinnerStatusTerminalReconcile.ts';

type AssistantRenderIntent = 'streamingChrome' | 'runningUpdate' | 'terminalFinalize' | 'idleRefresh' | 'activityToggle';

type AssistantRenderTransactionResult = {
    root: HTMLElement;
    changed: boolean;
    requiresPostRender: boolean;
    messageDomId: string;
};

type AssistantRenderReplacement = { nextMarkup: TrustedHtml; replacement?: never } | { nextMarkup?: never; replacement: HTMLElement };

type AssistantRenderTransactionArguments = AssistantRenderReplacement & {
    existingMessageRoot: HTMLElement;
    intent: AssistantRenderIntent;
    conversationId?: string;
    messageDomId: string;
    message: ChatMessage;
    comparisonTurn: ChatComparisonTurnRenderModel | null;
    viewportStabilityScope: AssistantViewportStabilityScope;
    assistantDomState?: AssistantDomStatePreservation | null;
    forceSettledAssistantBody?: boolean;
    updateConversationRenderCache?: AssistantRenderCacheUpdate;
};

type AssistantTransactionCacheCommitArguments = {
    conversationId: string;
    messageDomId: string;
    message: ChatMessage;
    comparisonTurn: ChatComparisonTurnRenderModel | null;
    updateConversationRenderCache?: AssistantRenderCacheUpdate;
};

const shouldPreserveText = (intent: AssistantRenderIntent): boolean => intent === 'streamingChrome' || intent === 'runningUpdate' || intent === 'terminalFinalize';

const shouldSuppressInsertAnimations = (intent: AssistantRenderIntent): boolean => intent === 'terminalFinalize' || intent === 'idleRefresh' || intent === 'activityToggle';

const shouldSettleLiveDom = (intent: AssistantRenderIntent): boolean => intent === 'terminalFinalize';

const shouldCommitRenderCache = (intent: AssistantRenderIntent): boolean => intent === 'terminalFinalize' || intent === 'idleRefresh';

const resolveEffectiveAssistantRenderIntent = (root: HTMLElement, intent: AssistantRenderIntent): AssistantRenderIntent => {
    if (intent === 'idleRefresh' && hasStreamingAssistantDom(root)) {
        return 'terminalFinalize';
    }
    return intent;
};

const commitAssistantTransactionRenderCache = (inputArguments: AssistantTransactionCacheCommitArguments): void => {
    commitAssistantRenderCacheUpdate({
        updateConversationRenderCache: inputArguments.updateConversationRenderCache,
        conversationId: inputArguments.conversationId,
        messageDomId: inputArguments.messageDomId,
        message: inputArguments.message,
        comparisonTurn: inputArguments.comparisonTurn
    });
};

const applyAssistantRenderTransaction = (inputArguments: AssistantRenderTransactionArguments): AssistantRenderTransactionResult => {
    const effectiveIntent = resolveEffectiveAssistantRenderIntent(inputArguments.existingMessageRoot, inputArguments.intent);
    const existingFeedback = dom.resolve('.message-error', inputArguments.existingMessageRoot);
    const previousFeedbackText = existingFeedback?.textContent;
    const messageText = resolveAssistantMessageParts(inputArguments.existingMessageRoot)?.text;
    if (effectiveIntent !== 'activityToggle' && messageText !== undefined) {
        cancelLoadingActivityTransition(messageText);
    }
    const previousTextSize = effectiveIntent === 'terminalFinalize' && messageText !== undefined ? measurePresenceSize(messageText) : null;
    const assistantDomState = inputArguments.assistantDomState ?? collectAssistantDomState(inputArguments.existingMessageRoot);
    const forceTextPatch = effectiveIntent === 'terminalFinalize' && inputArguments.forceSettledAssistantBody === true;
    let changed = false;
    let requiresPostRender = false;

    const applyMarkupToLiveTree = (): void => {
        const commonArguments: {
            existingMessageRoot: HTMLElement;
            mode: 'preserveText' | 'full';
            suppressInsertAnimations: boolean;
            assistantDomState: AssistantDomStatePreservation;
            forceTextPatch?: boolean;
            activityToggle?: boolean;
        } = {
            existingMessageRoot: inputArguments.existingMessageRoot,
            mode: shouldPreserveText(effectiveIntent) ? 'preserveText' : 'full',
            suppressInsertAnimations: shouldSuppressInsertAnimations(effectiveIntent),
            assistantDomState,
            ...(forceTextPatch ? { forceTextPatch: true } : {}),
            ...(effectiveIntent === 'activityToggle' ? { activityToggle: true } : {})
        };
        const applied =
            inputArguments.replacement === undefined
                ? applyRenderedAssistantMessageRoot({
                      ...commonArguments,
                      nextMarkup: inputArguments.nextMarkup
                  })
                : applyParsedAssistantMessageRoot({
                      ...commonArguments,
                      replacement: inputArguments.replacement
                  });
        changed = applied.changed;
        requiresPostRender = applied.requiresPostRender;
        if (shouldSettleLiveDom(effectiveIntent) && normalizeSettledAssistantDom(applied.root)) {
            changed = true;
            requiresPostRender = true;
        }
        if (effectiveIntent === 'terminalFinalize') {
            const feedback = dom.resolve('.message-error', applied.root);
            if (feedback instanceof HTMLElement && existingFeedback === null) prepareEnterWithPresence(feedback, true, true)();
            const bodyChanged = applied.requiresPostRender || previousFeedbackText !== feedback?.textContent;
            if (bodyChanged) {
                const area = optionalClosestElement(applied.root, CHAT_SELECTORS.MESSAGES_AREA);
                const actions = resolveAssistantMessageParts(applied.root)?.actions;
                const holdsOutgoingStatus = actions !== undefined && actions !== null && isSpinnerStatusTerminalTransitionActive(actions);
                if (area instanceof HTMLElement && (isMainTimelineAutoScrollLocked(area) || holdsOutgoingStatus) && messageText !== undefined && previousTextSize !== null) {
                    if (isPresenceMorphing(messageText)) stopPresenceAnimation(messageText);
                    const nextTextSize = measurePresenceSize(messageText);
                    const outgoingActions = dom.resolve('.message-action-buttons-left', applied.root);
                    const animation = nextTextSize === null ? null : animatePresenceMorph(messageText, previousTextSize, nextTextSize, { fadeChildren: false, preserveWrapping: true, ...(outgoingActions === null ? {} : { afterExitOf: outgoingActions }) });
                    if (animation !== null && outgoingActions !== null)
                        deferUntilPresenceExitsSettle(outgoingActions, () => {
                            if (!isMainTimelineAutoScrollLocked(area) && (animation.playState === 'paused' || animation.playState === 'running')) withAssistantViewportStability(applied.root, () => animation.finish());
                        });
                }
            }
        }
    };

    if (inputArguments.viewportStabilityScope === 'caller') {
        applyMarkupToLiveTree();
    } else {
        withAssistantViewportStability(inputArguments.existingMessageRoot, applyMarkupToLiveTree);
    }

    const conversationId = inputArguments.conversationId;
    if (shouldCommitRenderCache(effectiveIntent) && conversationId !== undefined) {
        commitAssistantTransactionRenderCache({
            conversationId,
            messageDomId: inputArguments.messageDomId,
            message: inputArguments.message,
            comparisonTurn: inputArguments.comparisonTurn,
            ...(inputArguments.updateConversationRenderCache !== undefined ? { updateConversationRenderCache: inputArguments.updateConversationRenderCache } : {})
        });
    }

    return {
        root: inputArguments.existingMessageRoot,
        changed,
        requiresPostRender,
        messageDomId: inputArguments.messageDomId
    };
};

export { applyAssistantRenderTransaction };
export type { AssistantRenderIntent, AssistantRenderTransactionResult };
