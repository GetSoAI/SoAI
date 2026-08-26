/* SoAI - Central assistant render transaction and render-signature commit [frontend/assets/ts/features/chat/message/assistantRenderTransaction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import { collectAssistantDomState, type AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { applyParsedAssistantMessageRoot, applyRenderedAssistantMessageRoot } from '@features/chat/message/assistantMessageMarkupPatching.ts';
import { commitAssistantRenderCacheUpdate, type AssistantRenderCacheUpdate } from '@features/chat/message/assistantRenderCacheUpdate.ts';
import { hasStreamingAssistantDom, normalizeSettledAssistantDom } from '@features/chat/message/assistantSettledDom.ts';
import { withAssistantViewportStability, type AssistantViewportStabilityScope } from '@features/chat/message/assistantViewportStability.ts';
import type { TrustedHtml } from '@core/security/public.ts';

type AssistantRenderIntent = 'streamingChrome' | 'runningUpdate' | 'terminalFinalize' | 'idleRefresh';

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

const shouldSuppressInsertAnimations = (intent: AssistantRenderIntent): boolean => intent === 'terminalFinalize' || intent === 'idleRefresh';

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
        } = {
            existingMessageRoot: inputArguments.existingMessageRoot,
            mode: shouldPreserveText(effectiveIntent) ? 'preserveText' : 'full',
            suppressInsertAnimations: shouldSuppressInsertAnimations(effectiveIntent),
            assistantDomState,
            ...(forceTextPatch ? { forceTextPatch: true } : {})
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
