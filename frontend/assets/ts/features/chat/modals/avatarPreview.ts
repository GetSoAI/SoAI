/* SoAI - Chat feature avatar preview [frontend/assets/ts/features/chat/modals/avatarPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { processAvatarFile } from '@features/chat/avatar/service.ts';

const AVATAR_PLACEHOLDER_SELECTOR = '.chat-avatar-preview-placeholder';

const optionalElement = (parent: Element, selector: string): Element | null => dom.resolve(selector, parent);

const optionalInputElement = (parent: Element, selector: string): HTMLInputElement | null => {
    const element = dom.resolve(selector, parent);
    if (!element) {
        return null;
    }
    if (!(element instanceof HTMLInputElement)) {
        throw new Error(`Chat avatar input must be an HTMLInputElement for selector: ${selector}`);
    }
    return element;
};

interface AvatarPreviewHost {
    optionalHTMLElement(selector: string, context?: Element): HTMLElement | null;
    runUiTask(operationId: string, task: () => Promise<void> | void): void;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    renderCurrentConversation(): Promise<void>;
    showNotification(message: string, type: NotificationType): void;
    avatarStorage: {
        getAssistantAvatar(): string | null;
        setAssistantAvatar(value: string | null): void;
        getUserAvatar(): string | null;
        setUserAvatar(value: string | null): void;
    };
    getAssistantAvatarIconHtml(): TrustedHtml;
    getUserAvatarIconHtml(): TrustedHtml;
}

interface AvatarUploadBinding {
    avatarRole: 'user' | 'assistant';
    previewSelector: string;
    fileInputSelector: string;
    removeButtonSelector: string;
    getAvatar: () => string | null;
    setAvatar: (value: string | null) => void;
    getDefaultIconHtml: () => TrustedHtml;
}

const createAvatarBindings = (host: AvatarPreviewHost): AvatarUploadBinding[] => [
    {
        avatarRole: 'user',
        previewSelector: '.user-avatar-preview',
        fileInputSelector: '.user-avatar-file-input',
        removeButtonSelector: '.user-avatar-remove-btn',
        getAvatar: () => host.avatarStorage.getUserAvatar(),
        setAvatar: (value) => host.avatarStorage.setUserAvatar(value),
        getDefaultIconHtml: () => host.getUserAvatarIconHtml()
    },
    {
        avatarRole: 'assistant',
        previewSelector: '.assistant-avatar-preview',
        fileInputSelector: '.assistant-avatar-file-input',
        removeButtonSelector: '.assistant-avatar-remove-btn',
        getAvatar: () => host.avatarStorage.getAssistantAvatar(),
        setAvatar: (value) => host.avatarStorage.setAssistantAvatar(value),
        getDefaultIconHtml: () => host.getAssistantAvatarIconHtml()
    }
];

const resolveAvatarUploadMessage = (avatarRole: AvatarUploadBinding['avatarRole'], message: 'saved' | 'tooLarge' | 'invalidType' | 'readFailed'): string => {
    if (avatarRole === 'user') {
        switch (message) {
            case 'saved':
                return i18n.t('chat.configuration.userAvatarSaved');
            case 'tooLarge':
                return i18n.t('chat.configuration.userAvatarTooLarge');
            case 'invalidType':
                return i18n.t('chat.configuration.userAvatarInvalidType');
            case 'readFailed':
                return i18n.t('chat.configuration.userAvatarReadFailed');
        }
    }
    switch (message) {
        case 'saved':
            return i18n.t('chat.configuration.assistantAvatarSaved');
        case 'tooLarge':
            return i18n.t('chat.configuration.assistantAvatarTooLarge');
        case 'invalidType':
            return i18n.t('chat.configuration.assistantAvatarInvalidType');
        case 'readFailed':
            return i18n.t('chat.configuration.assistantAvatarReadFailed');
    }
};

const ensurePlaceholderElement = (preview: HTMLElement, iconHtml: TrustedHtml): HTMLElement => {
    const existingPlaceholder = optionalElement(preview, AVATAR_PLACEHOLDER_SELECTOR);
    if (existingPlaceholder instanceof HTMLElement) {
        return existingPlaceholder;
    }
    const placeholder = document.createElement('span');
    placeholder.className = 'chat-avatar-preview-placeholder';
    placeholder.setAttribute('aria-hidden', 'true');
    dom.setHTML(placeholder, iconHtml, { escape: false });
    preview.appendChild(placeholder);
    return placeholder;
};

const updateAvatarPreview = (host: AvatarPreviewHost, modal: Element, binding: AvatarUploadBinding, dataUrl: string | null): void => {
    const preview = host.optionalHTMLElement(binding.previewSelector, modal);
    if (!preview) {
        return;
    }
    const placeholder = ensurePlaceholderElement(preview, binding.getDefaultIconHtml());
    const existingImage = optionalElement(preview, 'img');
    if (existingImage) {
        existingImage.remove();
    }
    if (dataUrl) {
        placeholder.classList.add('u-hidden');
        const img = document.createElement('img');
        img.src = dataUrl;
        img.alt = '';
        img.className = 'chat-avatar-image';
        preview.appendChild(img);
    } else {
        placeholder.classList.remove('u-hidden');
    }
    const removeButton = host.optionalHTMLElement(binding.removeButtonSelector, modal);
    if (removeButton) {
        removeButton.classList.toggle('u-hidden', !dataUrl);
    }
};

const initializeAvatarPreview = (host: AvatarPreviewHost, modal: Element): void => {
    const bindings = createAvatarBindings(host);
    for (const binding of bindings) {
        const preview = host.optionalHTMLElement(binding.previewSelector, modal);
        if (!preview) {
            continue;
        }
        ensurePlaceholderElement(preview, binding.getDefaultIconHtml());
        const currentAvatar = binding.getAvatar();
        updateAvatarPreview(host, modal, binding, currentAvatar);
    }
};

interface AvatarUploadRoots {
    inputsRoot: HTMLElement;
    resolvePreviewRoot: () => Element | null;
}

const updatePreviewIfAvailable = (host: AvatarPreviewHost, roots: AvatarUploadRoots, binding: AvatarUploadBinding, dataUrl: string | null): void => {
    const previewRoot = roots.resolvePreviewRoot();
    if (!previewRoot) {
        return;
    }
    updateAvatarPreview(host, previewRoot, binding, dataUrl);
};

const bindAvatarUploadEvents = (host: AvatarPreviewHost, roots: AvatarUploadRoots, signal: AbortSignal): void => {
    const bindings = createAvatarBindings(host);
    for (const binding of bindings) {
        const avatarInput = optionalInputElement(roots.inputsRoot, binding.fileInputSelector);
        if (!avatarInput) {
            continue;
        }
        avatarInput.addEventListener(
            'change',
            () => {
                const file = avatarInput.files?.[0];
                if (!file) {
                    return;
                }
                host.runUiTask('chat:avatarUpload', async () => {
                    try {
                        const result = await processAvatarFile(file);
                        binding.setAvatar(result.dataUrl);
                        updatePreviewIfAvailable(host, roots, binding, result.dataUrl);
                        host.showNotification(resolveAvatarUploadMessage(binding.avatarRole, 'saved'), 'success');
                        host.invalidateChatMarkup('current');
                        await host.renderCurrentConversation();
                    } catch (error) {
                        const errorMessage = ensureError(error).message;
                        if (errorMessage === 'AVATAR_TOO_LARGE') {
                            host.showNotification(resolveAvatarUploadMessage(binding.avatarRole, 'tooLarge'), 'error');
                        } else if (errorMessage === 'AVATAR_INVALID_TYPE') {
                            host.showNotification(resolveAvatarUploadMessage(binding.avatarRole, 'invalidType'), 'error');
                        } else {
                            host.showNotification(resolveAvatarUploadMessage(binding.avatarRole, 'readFailed'), 'error');
                        }
                    } finally {
                        avatarInput.value = '';
                    }
                });
            },
            { signal }
        );
    }
};

export { bindAvatarUploadEvents, initializeAvatarPreview };
