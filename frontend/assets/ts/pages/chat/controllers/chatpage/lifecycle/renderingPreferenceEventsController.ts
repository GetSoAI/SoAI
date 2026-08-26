/* SoAI - Chat lifecycle rendering preference event ownership [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/renderingPreferenceEventsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHANGED_EVENTS } from '@core/storage/service/constants.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';

interface ChatPageRenderingPreferenceEventsHost extends ChatConversationViewHost, ChatUiTaskScopeHost {
    dom: { getDocument(): Document };
}

const bindChatPageRenderingPreferenceEvents = (host: ChatPageRenderingPreferenceEventsHost, signal: AbortSignal): void => {
    const view = host.dom.getDocument().defaultView;
    if (!view) {
        return;
    }
    const handleLanguageChanged = (): void => {
        host.taskScope.run('chat:languageChanged', async () => {
            host.conversationView.refreshWorkerRendering();
            await host.conversationView.refresh();
            host.conversationView.initializeSearch();
        });
    };
    const handleLocalizationChanged = (): void => {
        host.taskScope.run('chat:localizationChanged', async () => {
            host.conversationView.refreshWorkerRendering();
            await host.conversationView.refresh();
        });
    };
    const handleCodeRecognitionChanged = (): void => {
        host.conversationView.invalidateMessagePresentation();
        host.taskScope.run('chat:renderCurrentConversation', async () => {
            await host.conversationView.renderCurrent();
        });
    };
    view.addEventListener('soai:language:changed', handleLanguageChanged, { signal });
    view.addEventListener('soai:localization:changed', handleLocalizationChanged, { signal });
    view.addEventListener(CHANGED_EVENTS.codeRecognition, handleCodeRecognitionChanged, { signal });
};

export { bindChatPageRenderingPreferenceEvents };
export type { ChatPageRenderingPreferenceEventsHost };
