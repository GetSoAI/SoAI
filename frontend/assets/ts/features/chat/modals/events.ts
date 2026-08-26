/* SoAI - Chat feature modals events [frontend/assets/ts/features/chat/modals/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { resolveChatParameterControlElement } from '@features/chat/parameters/parameterElementResolution.ts';

interface ChatConfigurationModalBindingsHost {
    runUiTask(operationId: string, task: () => Promise<void> | void): void;
    applyParameterValueFromElement(element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): void;
    optionalHTMLElement(selector: string, context?: Element): HTMLElement | null;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    renderCurrentConversation(): Promise<void>;
    showNotification(message: string, type: NotificationType): void;
    updateText(target: HTMLElement, text: string): void;
    avatarStorage: AvatarStorage;
    getAssistantAvatarIconHtml(): TrustedHtml;
    getUserAvatarIconHtml(): TrustedHtml;
}

interface AvatarStorage {
    getAssistantAvatar(): string | null;
    setAssistantAvatar(value: string | null): void;
    getUserAvatar(): string | null;
    setUserAvatar(value: string | null): void;
}

const bindChatConfigurationModalParameterEvents = (host: ChatConfigurationModalBindingsHost, modal: HTMLElement): (() => void) => {
    const abortController = new AbortController();
    const { signal } = abortController;

    const applyParameterFromEvent = (event: Event, operationId: string): void => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const parameterTarget = resolveChatParameterControlElement(target);
        if (!parameterTarget) {
            return;
        }
        host.runUiTask(operationId, () => host.applyParameterValueFromElement(parameterTarget));
    };

    const handleModalInput = (event: Event): void => applyParameterFromEvent(event, 'chat:modalParameterInput');
    modal.addEventListener('input', handleModalInput, { signal });

    const handleModalChange = (event: Event): void => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        applyParameterFromEvent(event, 'chat:modalParameterChange');
    };
    modal.addEventListener('change', handleModalChange, { signal });

    return (): void => {
        abortController.abort();
    };
};

export { bindChatConfigurationModalParameterEvents };
export type { ChatConfigurationModalBindingsHost };
