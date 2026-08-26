/* SoAI - Chat avatars, icons, color controls, and header presentation ownership [frontend/assets/ts/pages/chat/controllers/chatpage/presentation/ChatPagePresentationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import { hideConversationColorPicker, showConversationColorPicker } from '@pages/chat/controllers/page/dom/colorPicker.ts';
import type { ChatPageDomHost } from '@pages/chat/controllers/page/dom/contracts.ts';
import { insertIcons } from '@pages/chat/controllers/page/dom/icons.ts';
import { updateExportButtonVisibility, updateHeaderModelSelectorVisibility } from '@pages/chat/controllers/page/dom/input.ts';
import type { ChatPagePresentationContract } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import { ChatColorToolkit, resolveConversationExecutionState, type Conversation } from '@features/chat/public.ts';

interface ChatPagePresentationDependencies extends ChatPageDomHost, ChatTurnRuntimeOwner, ChatConversationStateHost, ChatSettingsStateHost, ChatViewStateHost, ChatUiTaskScopeHost, PageFeedbackOwnerHost {
    dom: ChatPageDomHost['dom'] & { getDocument(): Document };
}

class ChatPagePresentationController implements ChatPagePresentationContract {
    readonly #page: ChatPagePresentationDependencies;
    readonly #colors: ChatColorToolkit;

    constructor(page: ChatPagePresentationDependencies) {
        this.#page = page;
        this.#colors = new ChatColorToolkit({
            queryUI: (selector, container) => page.pageDom.query(selector, container),
            toggleClassName: (element, className, add) => page.pageDom.toggleClass(element, className, add),
            optionalUI: (selector, container) => page.pageDom.optionalHTMLElement(selector, container),
            dom: { getDocument: () => page.dom.getDocument() }
        });
    }

    assistantAvatarUrl(): string | null {
        return this.#page.settings.storage.getAssistantAvatar();
    }

    userAvatarUrl(): string | null {
        return this.#page.settings.storage.getUserAvatar();
    }

    cachedIcon(name: IconName, options: IconOptions = {}): TrustedHtml {
        return this.#page.viewState.iconCache.get(name, options, (iconName, iconOptions) => this.#page.services.getIconSync(iconName, iconOptions));
    }

    updateExportButtonVisibility(): void {
        updateExportButtonVisibility({
            pageDom: this.#page.pageDom,
            currentConversation: () => this.#currentConversation(),
            isConversationExecuting: (conversationId) => this.#isConversationExecuting(conversationId)
        });
    }

    updateHeaderModelSelectorVisibility(): void {
        updateHeaderModelSelectorVisibility(this.#page, this.#page.conversationState.models.length, this.#page.viewState.sidebarOpen, this.#page.services.isDetached());
    }

    insertIcons(): void {
        insertIcons(this.#page, this.#page.viewState.sidebarOpen, this.#page.viewState.showFavoritesAtTop, (name, options) => this.cachedIcon(name, options));
    }

    showConversationColorPicker(conversationItem: HTMLElement, conversationId: string): void {
        showConversationColorPicker({ ...this.#page, isConversationExecuting: (id) => this.#isConversationExecuting(id) }, this.#colors, conversationItem, conversationId, (name, options) => this.cachedIcon(name, options));
    }

    hideConversationColorPicker(): void {
        hideConversationColorPicker(this.#page);
    }

    conversationColorLabel(color: string | null): string | null {
        return this.#colors.getLabel(color);
    }

    #currentConversation(): Conversation | null {
        const conversationId = this.#page.conversationState.currentConversationId;
        return conversationId === null ? null : (this.#page.conversationState.conversations.get(conversationId) ?? null);
    }

    #isConversationExecuting(conversationId: string): boolean {
        return resolveConversationExecutionState({
            activeChatConversationIds: this.#page.conversationState.activeChatConversationIds,
            conversationId,
            isStreamingConversation: (candidateConversationId) => this.#page.turnRuntime.requireStreaming().isStreamingConversation(candidateConversationId),
            isAgentRenderingActive: (candidateConversationId) => this.#page.turnRuntime.requireAgent().isRenderingActive(candidateConversationId)
        }).isExecuting;
    }
}

export { ChatPagePresentationController };
export type { ChatPagePresentationContract, ChatPagePresentationDependencies };
export type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
