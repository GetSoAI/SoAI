/* SoAI - Chat feature sync spinner [frontend/assets/ts/features/chat/chatuimanager/syncSpinner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';

export function showSyncSpinner(context: ChatUIManagerContext): void {
    const messagesArea = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messagesArea instanceof HTMLElement)) {
        return;
    }

    const overlayCandidate = context.dependencies.optionalUI('.chat-sync-overlay', messagesArea);
    let overlay = overlayCandidate instanceof HTMLElement ? overlayCandidate : null;

    if (!overlay) {
        const doc = context.dependencies.dom.getDocument();
        const loadingLabel = i18n.t('chat.sync.loading');

        overlay = doc.createElement('div');
        overlay.className = 'chat-sync-overlay';
        setAriaBusy(overlay, true);
        overlay.setAttribute('aria-label', loadingLabel);

        const spinner = doc.createElement('div');
        spinner.className = 'chat-sync-spinner';
        spinner.setAttribute('aria-hidden', 'true');

        const label = doc.createElement('div');
        label.className = 'chat-sync-label';
        label.textContent = loadingLabel;

        overlay.appendChild(spinner);
        overlay.appendChild(label);
        messagesArea.appendChild(overlay);
    }

    overlay.classList.add('is-syncing');
}

export function hideSyncSpinner(context: ChatUIManagerContext): void {
    const messagesArea = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messagesArea instanceof HTMLElement)) {
        return;
    }

    const overlay = context.dependencies.optionalUI('.chat-sync-overlay', messagesArea);
    if (overlay) {
        overlay.remove();
    }
}
