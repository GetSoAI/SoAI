/* SoAI - Shared license service implementation [frontend/assets/ts/core/licenseservice/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getClipboardService } from '@core/clipboard.ts';
import { dom } from '@core/dom/dom.ts';
import { getDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isString } from '@core/typeGuards.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { ensureTranslationsReady, fetchLicenseData, fetchRequirementsText } from '@core/licenseservice/actions.ts';
import { TEXT_MODAL_CONFIGS } from '@core/licenseservice/constants.ts';
import { resolveTextModalButtons, resolveTextModalContent } from '@core/licenseservice/dom.ts';
import { isClipboardService, isLicenseService } from '@core/licenseservice/guards.ts';
import type { ClipboardServiceInterface, CreateButtonOptions, LicenseData, LicenseServiceInterface, TextModalKey } from '@core/licenseservice/types.ts';
import { parseNotificationType } from '@core/ui/notifications/notificationTypeParsing.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

class LicenseService implements LicenseServiceInterface {
    licenseData: LicenseData | null;
    creditsText: string | null;
    clipboard: ClipboardServiceInterface | null;
    resources: ResourceTracker;

    constructor() {
        this.licenseData = null;
        this.creditsText = null;
        const clipboardService = getClipboardService();
        this.clipboard = isClipboardService(clipboardService) ? clipboardService : null;
        this.resources = new ResourceTracker();
    }

    async initialize(): Promise<void> {
        await ensureTranslationsReady();
    }

    async fetchLicenseData(): Promise<LicenseData> {
        if (this.licenseData) {
            return this.licenseData;
        }
        const payload = await fetchLicenseData();
        this.licenseData = payload;
        return payload;
    }

    private async fetchCreditsText(): Promise<string | null> {
        if (this.creditsText !== null) {
            return this.creditsText;
        }
        const payload = await fetchRequirementsText();
        if (!payload) {
            return null;
        }
        this.creditsText = payload;
        return payload;
    }

    private renderLoadingState(key: TextModalKey, loadingMessage: string): HTMLElement {
        const config = TEXT_MODAL_CONFIGS[key];
        const modalRoot = requireModalPresenter().requireElement(config.id);
        const textElement = resolveTextModalContent(config.id, modalRoot);
        if (!textElement) {
            throw new Error(`${key} text element is missing`);
        }
        this.setCopyButtonEnabled(key, false);
        dom.setText(textElement, '');
        dom.addClass(textElement, 'is-loading');
        const doc = getDocument();
        if (!doc) {
            throw new Error(`Document unavailable while rendering ${key} content`);
        }
        const spinner = doc.createElement('span');
        spinner.className = 'loading-spinner';
        const loadingText = doc.createElement('span');
        loadingText.className = 'loading-text';
        loadingText.textContent = loadingMessage;
        textElement.appendChild(spinner);
        textElement.appendChild(loadingText);
        return textElement;
    }

    private setCopyButtonEnabled(key: TextModalKey, enabled: boolean): void {
        const config = TEXT_MODAL_CONFIGS[key];
        const modalRoot = requireModalPresenter().requireElement(config.id);
        const { copyButton } = resolveTextModalButtons(config.id, modalRoot);
        if (!copyButton) {
            return;
        }
        copyButton.disabled = !enabled;
    }

    private async showTextModal(
        key: TextModalKey,
        {
            loadingMessage,
            unavailableMessage,
            loadText
        }: {
            loadingMessage: string;
            unavailableMessage: string;
            loadText: () => Promise<string | null>;
        }
    ): Promise<void> {
        await this.initialize();
        const config = TEXT_MODAL_CONFIGS[key];
        const presenter = requireModalPresenter();
        presenter.requireElement(config.id);
        const textElement = this.renderLoadingState(key, loadingMessage);
        presenter.open(config.id);
        try {
            const text = await loadText();
            dom.removeClass(textElement, 'is-loading');
            if (isString(text) && text.length > 0) {
                dom.setText(textElement, text);
                this.setCopyButtonEnabled(key, true);
                return;
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('LicenseService', `Failed to load "${key}" content`, runtimeError);
            dom.removeClass(textElement, 'is-loading');
        }
        dom.setText(textElement, unavailableMessage);
        this.setCopyButtonEnabled(key, false);
    }

    async showLicense(): Promise<void> {
        await this.showTextModal('license', {
            loadingMessage: i18n.t('about.loadingLicense'),
            unavailableMessage: i18n.t('about.licenseUnavailable'),
            loadText: async () => {
                const data = await this.fetchLicenseData();
                return isString(data.licenseText) && data.licenseText.length > 0 ? data.licenseText : null;
            }
        });
    }

    async showCredits(): Promise<void> {
        await this.showTextModal('credits', {
            loadingMessage: i18n.t('about.loadingCredits'),
            unavailableMessage: i18n.t('about.creditsUnavailable'),
            loadText: async () => await this.fetchCreditsText()
        });
    }

    createLicenseButton(options: CreateButtonOptions = {}): HTMLButtonElement {
        const { text = null, className = 'ui-button ui-button--sm', id = null } = options;
        if (!isString(text) || !text.trim()) {
            throw new Error('License button requires a translated text label');
        }
        const doc = getDocument();
        if (!doc) {
            throw new Error('Document unavailable for license button');
        }
        const button = doc.createElement('button');
        dom.setText(button, text.trim());
        const classes = className.split(/\s+/).filter(Boolean);
        dom.addClass(button, classes);
        if (id) {
            button.id = id;
        }
        this.resources.addEventListener(button, 'click', async (event: Event) => {
            event.preventDefault();
            await this.showLicense();
        });
        return button;
    }

    async handleCopy(key: TextModalKey): Promise<void> {
        const config = TEXT_MODAL_CONFIGS[key];
        const presenter = requireModalPresenter();
        const modalRoot = presenter.requireElement(config.id);
        const copyButton = resolveTextModalButtons(config.id, modalRoot).copyButton;
        if (copyButton?.disabled === true) {
            return;
        }
        const textElement = resolveTextModalContent(config.id, modalRoot);
        const textToCopy = textElement?.textContent ?? '';
        if (textToCopy.length === 0) {
            this.notifyCopyError();
            return;
        }
        const clipboard = this.clipboard;
        if (!clipboard) {
            this.notifyCopyError();
            return;
        }
        await clipboard.copyText(textToCopy, {
            successMessage: i18n.t('about.copySuccess'),
            errorMessage: i18n.t('about.copyError'),
            notify: (message: string, type: string) => showNotification(message, parseNotificationType(type))
        });
    }

    notifyCopyError(message: string | null = null): void {
        const resolvedMessage = message !== null ? message : i18n.t('about.copyError');
        showNotification(resolvedMessage, 'error');
    }
}

const createLicenseService = (): LicenseService => new LicenseService();

const getLicenseService = (): LicenseServiceInterface => {
    const candidate = resolveKernelService('core.licenseService');
    if (!isLicenseService(candidate)) {
        throw new Error('core.licenseService is not registered');
    }
    return candidate;
};

const showLicenseModal = (): Promise<void> => getLicenseService().showLicense();

const showCreditsModal = (): Promise<void> => getLicenseService().showCredits();

export { createLicenseService, getLicenseService, LicenseService, showCreditsModal, showLicenseModal };
