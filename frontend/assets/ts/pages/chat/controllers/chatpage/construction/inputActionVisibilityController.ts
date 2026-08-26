/* SoAI - Chat page input action visibility controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/inputActionVisibilityController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { updateHeaderFavoriteButton, updateHeaderToolsToggleButton } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { VisionSupportHost } from '@pages/chat/controllers/page/guards/modelVisionSupportController.ts';
import { applyInputActionVisibility } from '@pages/chat/controllers/page/dom/input.ts';
import type { ChatPageDomHost } from '@pages/chat/controllers/page/dom/contracts.ts';
import type { ChatTurnRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

interface InputActionVisibilityLifecycleHost extends ChatPageDomHost, VisionSupportHost, ChatSettingsStateHost, ChatUiTaskScopeHost, ChatPagePresentationHost, ChatConversationViewHost, ChatVoiceSessionHost {
    turnRuntime: ChatTurnRuntime;
    syncTokenCounterEnabledState(): void;
}

const createHeaderActionHost = (host: InputActionVisibilityLifecycleHost) => ({
    presentation: {
        pageDom: host.pageDom,
        getCachedIcon: (name: Parameters<typeof host.presentation.cachedIcon>[0], options: Parameters<typeof host.presentation.cachedIcon>[1]) => host.presentation.cachedIcon(name, options)
    },
    conversations: {
        getCurrentConversationId: () => host.conversationView.current()?.id ?? null,
        getConversationById: (conversationId: string) => {
            const conversation = host.conversationView.current();
            return conversation?.id === conversationId ? conversation : null;
        },
        isConversationExecuting: (conversationId: string) => host.conversationView.isExecuting(conversationId)
    }
});

const syncTokenCounterEnabledState = (host: InputActionVisibilityLifecycleHost): void => {
    host.syncTokenCounterEnabledState();
};

const stopUnavailableAudioActions = (host: InputActionVisibilityLifecycleHost): void => {
    const voiceEnabled = host.settings.parameters.inputActionVoiceEnabled === true;
    const callEnabled = host.settings.parameters.inputActionCallEnabled === true;
    if (!voiceEnabled) {
        host.voiceSession.cancelRecording();
    }
    if (!callEnabled && host.voiceSession.isCallActive()) {
        host.taskScope.run('chat:voiceCallDisabled', () => host.voiceSession.stopCall('disabled'));
    }
};

const applyInputActionVisibilityLifecycle = (host: InputActionVisibilityLifecycleHost): void => {
    applyInputActionVisibility(host, host.settings.parameters, (name, options) => host.presentation.cachedIcon(name, options));
    host.pageDom.query('.chat-input-actions').forEach((element) => host.pageDom.toggleClass(element, 'chat-input-actions--hydrating', false));
    syncTokenCounterEnabledState(host);
    const headerHost = createHeaderActionHost(host);
    updateHeaderFavoriteButton(headerHost);
    updateHeaderToolsToggleButton(headerHost);
    host.presentation.updateExportButtonVisibility();
    host.turnRuntime.optionalAgent()?.updateUiForCurrentConversation();
    stopUnavailableAudioActions(host);
};

export { applyInputActionVisibilityLifecycle };
