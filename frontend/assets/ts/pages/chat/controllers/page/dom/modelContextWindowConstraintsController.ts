/* SoAI - Applies max completion tokens constraints derived from the selected model context window [frontend/assets/ts/pages/chat/controllers/page/dom/modelContextWindowConstraintsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveModelContextWindowLimit } from '@core/chat/modelContextWindowLimit.ts';
import { isNumber } from '@core/typeGuards.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/public.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ModelContextWindowConstraintsHost extends ChatConversationRuntimeOwner, ChatConversationStateHost, ChatSettingsStateHost, PageDomOwnerHost {}

export const applyModelContextWindowConstraints = (host: ModelContextWindowConstraintsHost): void => {
    const currentModel = host.conversationState.currentModel;
    const modelData = currentModel ? host.conversationState.modelIndex.get(currentModel) : undefined;
    const contextWindow = resolveModelContextWindowLimit(host.settings.parameters.contextWindowTokens, modelData?.contextWindowTokens);
    const maxCompletionTokensInput = host.pageDom.query(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'max-completion-tokens-input'))[0];
    if (!(maxCompletionTokensInput instanceof HTMLInputElement)) {
        return;
    }
    if (isNumber(contextWindow) && contextWindow > 0) {
        maxCompletionTokensInput.max = String(contextWindow);
        if (isNumber(host.settings.parameters.maxCompletionTokens) && host.settings.parameters.maxCompletionTokens > contextWindow) {
            host.settings.parameters.maxCompletionTokens = contextWindow;
            maxCompletionTokensInput.value = String(contextWindow);
            host.conversationRuntime.requireStorage().saveState();
        }
        return;
    }
    maxCompletionTokensInput.max = '';
};
