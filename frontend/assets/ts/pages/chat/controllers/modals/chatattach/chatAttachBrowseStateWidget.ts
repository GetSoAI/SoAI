/* SoAI - Chat attach browse state widget [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachBrowseStateWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderInlineLoadingStatus } from '@core/ui/loadingStatus.ts';

const renderBrowseMessage = (container: HTMLElement, title: string, subtitle: string, loading = false): void => {
    const state = document.createElement('div');
    state.className = 'chat-attach-empty-state';
    const heading = document.createElement('strong');
    heading.className = loading ? 'chat-attach-empty-state-title inline-loading-status' : 'chat-attach-empty-state-title';
    renderInlineLoadingStatus(heading, { text: title, loading });
    const body = document.createElement('p');
    body.className = 'chat-attach-modal-hint';
    body.textContent = subtitle;
    state.append(heading, body);
    container.replaceChildren(state);
};

const setBrowseFooterButtonState = (button: HTMLButtonElement, active: boolean, enabled: boolean): void => {
    button.hidden = !active;
    button.disabled = !active || !enabled;
    button.setAttribute('aria-disabled', active && enabled ? 'false' : 'true');
};

export { renderBrowseMessage, setBrowseFooterButtonState };
