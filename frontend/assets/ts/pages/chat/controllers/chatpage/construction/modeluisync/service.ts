/* SoAI - Chat page model UI synchronization service [frontend/assets/ts/pages/chat/controllers/chatpage/construction/modeluisync/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { CHAT_EVENT_MODEL_SELECTION_CHANGED } from '@features/chat/public.ts';
import { syncAssistantHeaderActivities } from '@pages/chat/controllers/page/dom/effects.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';

interface ModelSelectionNotificationHost {
    currentModel: string | null;
    getLastNotifiedModelSelection(): string | null;
    setLastNotifiedModelSelection(modelId: string | null): void;
    dispatchEvent(event: Event): void;
}

interface AssistantHeaderCatalogStateHost extends ChatConversationStateHost {
    stateManager: { status: { normalizeStatus(status: JsonValue): string } };
    getDomContext(): Element | null;
}

const notifyModelSelectionChangedIfNeeded = (host: ModelSelectionNotificationHost): void => {
    const current = typeof host.currentModel === 'string' && host.currentModel.trim() ? host.currentModel.trim() : null;
    if (current === host.getLastNotifiedModelSelection()) {
        return;
    }
    host.setLastNotifiedModelSelection(current);
    host.dispatchEvent(new Event(CHAT_EVENT_MODEL_SELECTION_CHANGED));
};

const syncAssistantHeaderCatalogStateForPage = (host: AssistantHeaderCatalogStateHost, root?: Element): void => {
    const rootCandidate = root ?? host.getDomContext();
    if (!(rootCandidate instanceof Element)) {
        return;
    }
    syncAssistantHeaderActivities({
        root: rootCandidate,
        modelIndex: host.conversationState.modelIndex,
        statusManager: host.stateManager.status
    });
};

export { notifyModelSelectionChangedIfNeeded, syncAssistantHeaderCatalogStateForPage };
export type { AssistantHeaderCatalogStateHost, ModelSelectionNotificationHost };
