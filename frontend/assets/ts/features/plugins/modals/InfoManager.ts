/* SoAI - Plugins feature info manager [frontend/assets/ts/features/plugins/modals/InfoManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { PLUGIN_INFO_MODAL_ID } from '@features/plugins/modals/pluginInfoModal.ts';
import type { InfoManagerHost, InfoManagerOptions, InfoState, PluginCapabilityDescriptor } from '@features/plugins/modals/info/types.ts';
import { renderPluginInfoHtml } from '@features/plugins/modals/info/view.ts';

class InfoManager {
    readonly modalId = PLUGIN_INFO_MODAL_ID;
    readonly #host: InfoManagerHost;
    private security: InfoManagerOptions['security'];
    readonly #getCapabilityDescriptors: InfoManagerOptions['getCapabilityDescriptors'];
    state: InfoState;

    constructor({ host, security, getCapabilityDescriptors }: InfoManagerOptions) {
        if (!host) {
            throw new Error('InfoManager requires a host');
        }
        if (!security) {
            throw new Error('InfoManager requires a security module');
        }
        if (typeof getCapabilityDescriptors !== 'function') {
            throw new Error('InfoManager requires a getCapabilityDescriptors callback');
        }
        this.#host = host;
        this.state = this.#createInitialState();
        this.security = security;
        this.#getCapabilityDescriptors = getCapabilityDescriptors;
    }

    #createInitialState(): InfoState {
        return {
            currentInfoPlugin: null
        };
    }

    #clearModalState(): void {
        const modalRoot = this.#host.modals.requireElement(this.modalId);
        const container = this.#host.optionalHTMLElement(modalUiSelector(this.modalId, 'content'), modalRoot);
        if (container) {
            this.#host.updateHTML(container, '');
        }
        this.state.currentInfoPlugin = null;
    }

    onModalClosed(): void {
        this.#clearModalState();
    }

    disposeForPageDestroy(): void {
        this.#clearModalState();
    }

    async copyPluginInfo(): Promise<void> {
        if (!this.state.currentInfoPlugin) {
            throw new Error('InfoManager copy requires an active plugin');
        }

        const jsonString = JSON.stringify(this.state.currentInfoPlugin, null, 2);
        try {
            await copyTextWithHostClipboardFeedback(
                {
                    copyToClipboard: (text, options) => this.#host.copyToClipboard(text, options),
                    hasClipboardSupport: () => this.#host.hasClipboardSupport(),
                    showNotification: (message, type): void => this.#host.showNotification(message, type)
                },
                {
                    text: jsonString,
                    successMessage: i18n.t('common.clipboard.copied'),
                    errorMessage: i18n.t('plugins.notifications.pluginInfoCopyFailed'),
                    unavailableMessage: i18n.t('plugins.notifications.pluginInfoCopyFailed'),
                    unavailableType: 'error'
                }
            );
        } catch (error) {
            errorHandler.warn('InfoManager', 'Plugin info copy failed', ensureError(error));
        }
    }

    openPluginInfoModal = (plugin: PluginRecord): void => {
        if (!plugin?.name) {
            throw new Error('InfoManager requires a plugin with a name');
        }

        const modalRoot = this.#host.modals.requireElement(this.modalId);
        const container = this.#host.requireHTMLElement(modalUiSelector(this.modalId, 'content'), modalRoot);
        this.state.currentInfoPlugin = plugin;
        const capabilityDescriptors = (() => {
            const descriptors = this.#getCapabilityDescriptors(plugin);
            if (!Array.isArray(descriptors)) {
                throw new Error('InfoManager getCapabilityDescriptors must return an array');
            }
            return descriptors.filter((candidate): candidate is PluginCapabilityDescriptor => Boolean(candidate));
        })();
        const content = renderPluginInfoHtml(
            plugin,
            {
                host: this.#host,
                security: this.security
            },
            capabilityDescriptors
        );
        this.#host.updateHTML(container, content);
        this.#host.modals.open(this.modalId);
    };
}

export { InfoManager };
export type { InfoManagerHost } from '@features/plugins/modals/info/types.ts';
