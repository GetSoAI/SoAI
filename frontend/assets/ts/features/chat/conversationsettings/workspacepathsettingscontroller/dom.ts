/* SoAI - Chat conversation workspace-path DOM resolution [frontend/assets/ts/features/chat/conversationsettings/workspacepathsettingscontroller/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';

const resolveWorkspacePathPathElement = (modal: Element | null): HTMLInputElement | null => {
    if (!modal) {
        return null;
    }
    const element = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'chat-files-folder-path'), modal);
    return element instanceof HTMLInputElement ? element : null;
};

const resolveWorkspacePathStatusElement = (modal: Element | null): HTMLElement | null => {
    if (!modal) {
        return null;
    }
    const element = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'chat-files-folder-status'), modal);
    return element instanceof HTMLElement ? element : null;
};

const resolveWorkspacePathChangeButton = (modal: Element | null): HTMLButtonElement | null => {
    if (!modal) {
        return null;
    }
    const element = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'chat-files-folder-change-btn'), modal);
    return element instanceof HTMLButtonElement ? element : null;
};

const resolveWorkspacePathResetButton = (modal: Element | null): HTMLButtonElement | null => {
    if (!modal) {
        return null;
    }
    const element = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'chat-files-folder-reset-btn'), modal);
    return element instanceof HTMLButtonElement ? element : null;
};

export { resolveWorkspacePathChangeButton, resolveWorkspacePathPathElement, resolveWorkspacePathResetButton, resolveWorkspacePathStatusElement };
