/* SoAI - Chat page setup [frontend/assets/ts/pages/chat/controllers/page/events/setup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { isChatActionId } from '@features/chat/public.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { handleRootActionClick, handleRootBlur, handleRootChange, handleRootInput, handleRootPointerDown, handleRootPointerOut, handleRootPointerOver } from '@pages/chat/controllers/page/events/handlers.ts';
import { handleRootKeydown } from '@pages/chat/controllers/page/events/keyboardController.ts';
import { bindChatHoldShortcuts } from '@pages/chat/controllers/page/events/ChatHoldShortcutDomain.ts';

const bindChatActionClicks = (host: ChatRootEventsHost, root: HTMLElement, signal: AbortSignal): void => {
    bindDataActionListener({
        root,
        eventType: 'click',
        signal,
        isAction: isChatActionId,
        preventDefault: 'never',
        onAction: ({ event, action, actionElement }): void => handleRootActionClick(host, event, action, actionElement)
    });
};

const setupChatRootEvents = (host: ChatRootEventsHost, signal: AbortSignal, options: { includeClick?: boolean } = {}): void => {
    const root = host.shell.ensureRootElement();
    const includeClick = options.includeClick !== false;
    bindChatHoldShortcuts(host, root, signal);
    const handlePointerOver = (event: Event): void => handleRootPointerOver(host, event);
    const handlePointerOut = (event: Event): void => handleRootPointerOut(host, event);
    const handlePointerDown = (event: Event): void => handleRootPointerDown(host, event);
    const handleInput = (event: Event): void => handleRootInput(host, event);
    const handleChange = (event: Event): void => handleRootChange(host, event);
    const handleKeydown = (event: Event): void => handleRootKeydown(host, event);
    const handleBlur = (event: Event): void => handleRootBlur(host, event);
    const handleDocumentKeydown = (event: Event): void => host.shell.sidebarPeek.handleKeydown(event);
    bindEventGroup(
        [
            { target: root, type: 'pointerover', listener: handlePointerOver },
            { target: root, type: 'pointerout', listener: handlePointerOut },
            { target: root, type: 'pointerdown', listener: handlePointerDown },
            { target: root, type: 'input', listener: handleInput },
            { target: root, type: 'change', listener: handleChange },
            { target: root, type: 'keydown', listener: handleKeydown },
            { target: root, type: 'blur', listener: handleBlur, options: { capture: true } },
            { target: root.ownerDocument, type: 'keydown', listener: handleDocumentKeydown }
        ],
        signal
    );
    if (includeClick) {
        bindChatActionClicks(host, root, signal);
    }
};

export { bindChatActionClicks, setupChatRootEvents };
