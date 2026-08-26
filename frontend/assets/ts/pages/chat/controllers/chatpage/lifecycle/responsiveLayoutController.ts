/* SoAI - Chat page responsive layout controller [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/responsiveLayoutController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { CHAT_ACTIVITY_COMPACT_BREAKPOINT_PX, CHAT_SELECTORS, resolveActivityDurationDisplayMode, type ChatActivityDurationDisplayMode } from '@features/chat/public.ts';
import { applyWidescreenMode, type ChatUiBehaviorsOwner } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import { reconcileActivityDurationLifecycle } from '@pages/chat/controllers/chatpage/lifecycle/activityDurationLifecycleRuntime.ts';

interface ChatResponsiveLayoutDependencies extends ChatConversationStateHost, ChatRuntimeServicesHost, ChatConversationViewHost, ChatModelSessionHost, ChatUiTaskScopeHost, PageDomOwnerHost, ChatUiBehaviorsOwner {
    document: Document;
}

class ChatResponsiveLayoutSession {
    readonly #owners: ChatResponsiveLayoutDependencies;
    #activityDurationDisplayMode: ChatActivityDurationDisplayMode;

    constructor(owners: ChatResponsiveLayoutDependencies) {
        this.#owners = owners;
        this.#activityDurationDisplayMode = this.#resolveActivityDurationDisplayMode();
    }

    sync(): void {
        const nextDisplayMode = this.#resolveActivityDurationDisplayMode();
        const durationDisplayModeChanged = nextDisplayMode !== this.#activityDurationDisplayMode;
        this.#activityDurationDisplayMode = nextDisplayMode;
        void Promise.resolve(this.#owners.uiBehaviors.layout.applySidebarState()).catch((error) => {
            errorHandler.warn('ChatResponsiveLayoutSession', 'Failed to apply the chat sidebar state', ensureError(error));
        });
        applyWidescreenMode(this.#owners.uiBehaviors);
        if (durationDisplayModeChanged) {
            reconcileActivityDurationLifecycle(this.#owners);
            this.#owners.conversationView.refreshWorkerRendering();
            this.#owners.taskScope.run('chat:activityDurationDisplayModeChanged', () => this.#owners.conversationView.renderCurrent());
        }
        const messages = this.#owners.pageDom.optional(CHAT_SELECTORS.MESSAGES_CONTAINER);
        if (!(messages instanceof HTMLElement)) return;
        const conversationId = this.#owners.conversationState.currentConversationId;
        const activeComparisonRun = conversationId ? this.#owners.conversationView.activeComparisonRun(conversationId) : null;
        this.#owners.modelSession.syncComparisonPresentation(messages, {
            isCurrentStreaming: Boolean(conversationId && this.#owners.conversationView.isStreaming(conversationId)),
            activeComparisonRun
        });
    }

    #resolveActivityDurationDisplayMode(): ChatActivityDurationDisplayMode {
        return resolveActivityDurationDisplayMode(measureLayoutViewport(this.#owners.document).width, CHAT_ACTIVITY_COMPACT_BREAKPOINT_PX);
    }
}

export { ChatResponsiveLayoutSession };
export type { ChatResponsiveLayoutDependencies };
