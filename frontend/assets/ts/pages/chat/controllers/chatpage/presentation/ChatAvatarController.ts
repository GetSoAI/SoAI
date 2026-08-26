/* SoAI - Chat avatar selection and removal ownership [frontend/assets/ts/pages/chat/controllers/chatpage/presentation/ChatAvatarController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { handleAvatarRemove, triggerAvatarFileInput } from '@pages/chat/controllers/chatpage/construction/avatarHandlers.ts';
import type { ChatConversationViewContract } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatUiTaskScopeContract } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ChatAvatarDependencies {
    conversationView: ChatConversationViewContract;
    settings: ChatSettingsState;
    taskScope: ChatUiTaskScopeContract;
    pageDom: PageDom;
    feedback: PageFeedback;
}

class ChatAvatarController {
    readonly #dependencies: ChatAvatarDependencies;

    constructor(dependencies: ChatAvatarDependencies) {
        this.#dependencies = dependencies;
    }

    uploadUser(): void {
        triggerAvatarFileInput(this.#dependencies, '.user-avatar-file-input');
    }

    removeUser(): void {
        handleAvatarRemove(this.#dependencies, () => this.#dependencies.settings.storage.setUserAvatar(null), '.user-avatar-preview', '.user-avatar-remove-btn', i18n.t('chat.configuration.userAvatarRemoved'));
    }

    uploadAssistant(): void {
        triggerAvatarFileInput(this.#dependencies, '.assistant-avatar-file-input');
    }

    removeAssistant(): void {
        handleAvatarRemove(this.#dependencies, () => this.#dependencies.settings.storage.setAssistantAvatar(null), '.assistant-avatar-preview', '.assistant-avatar-remove-btn', i18n.t('chat.configuration.assistantAvatarRemoved'));
    }
}

export { ChatAvatarController };
export type { ChatAvatarDependencies };
