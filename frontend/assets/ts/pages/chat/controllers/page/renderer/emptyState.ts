/* SoAI - Chat page control layer renderer empty state [frontend/assets/ts/pages/chat/controllers/page/renderer/emptyState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { resolveAgentMode } from '@features/chat/public.ts';
import { resolveConversationAuthorityLock } from '@core/chat/conversationAuthorityLock.ts';
import { initializeChatEmptyStateNav } from '@pages/chat/controllers/chatUiVisibility.ts';
import type { ChatCurrentConversationRenderDependencies } from '@pages/chat/controllers/page/renderer/contracts.ts';

const getEmptyStateHTML = (host: ChatCurrentConversationRenderDependencies): TrustedHtml => {
    const conversation = host.conversationView.current();
    return host.emptyState.buildMarkup({
        sanitizer: host.pageContext.sanitizer,
        getCachedIcon: (name: IconName, options?: IconOptions) => host.presentation.cachedIcon(name, options),
        activeAgentMode: resolveAgentMode(conversation),
        authorityLock: resolveConversationAuthorityLock(conversation),
        ctrlEnterSendRequired: host.settings.parameters.ctrlEnterSendEnabled === true,
        isMac: navigator.platform.toUpperCase().indexOf('MAC') >= 0
    });
};

const initializeEmptyStateNav = (host: ChatCurrentConversationRenderDependencies, container: Element): void => {
    const abortController = host.pageLifecycle.listenersController;
    if (!abortController) {
        return;
    }
    initializeChatEmptyStateNav(host.emptyState, container, abortController.signal);
};

export { getEmptyStateHTML, initializeEmptyStateNav };
