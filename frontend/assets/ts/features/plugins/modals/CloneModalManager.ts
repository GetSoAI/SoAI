/* SoAI - Plugins feature clone modal manager [frontend/assets/ts/features/plugins/modals/CloneModalManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { validateClassNames } from '@core/ui/classNames.ts';
import { setElementDisabledState } from '@features/plugins/contracts/pluginPageSupport.ts';
import { CLONE_PLUGIN_MODAL_ID } from '@features/plugins/modals/clonePluginModal.ts';
import { executePluginCloneAction } from '@features/plugins/modals/clone/effects.ts';
import { isCloneProgressReporter } from '@features/plugins/modals/clone/guards.ts';
import { createInitialCloneState, isPluginCloneSupported, isValidCloneTargetName, resolveCloneTargetName, resolvePluginDisplayName } from '@features/plugins/modals/clone/service.ts';
import type { CloneManagerOptions, CloneOptions, CloneProgressReporter, CloneState } from '@features/plugins/modals/clone/types.ts';
import { renderClonePluginInfoMarkup } from '@features/plugins/modals/clone/view.ts';

class CloneModalManager {
    readonly modalId = CLONE_PLUGIN_MODAL_ID;
    readonly #host: CloneManagerOptions['host'];
    private classNames: Pick<Required<CloneManagerOptions['classNames']>, 'hidden' | 'disabled'>;
    private security: CloneManagerOptions['security'];
    state: CloneState;
    #cloneProgressReporter: CloneProgressReporter | null = null;
    #listenerDisposers: Array<() => void> = [];

    constructor({ host, classNames, security }: CloneManagerOptions) {
        if (!host) {
            throw new Error('CloneManager requires a host');
        }
        this.#host = host;
        this.state = createInitialCloneState();
        this.classNames = validateClassNames(classNames, ['hidden', 'disabled'], 'CloneManager');
        if (!security) {
            throw new Error('CloneManager requires a security module');
        }
        this.security = security;
    }

    #requireCloneProgressReporter(): CloneProgressReporter {
        if (this.#cloneProgressReporter) {
            return this.#cloneProgressReporter;
        }
        const candidate = this.#host.execution.createOperationProgressReporter(modalUiId(this.modalId, 'progress-container'), {
            cancelSelector: null,
            showCancel: false
        });
        if (!isCloneProgressReporter(candidate)) {
            throw new Error('CloneManager requires a valid progress reporter');
        }
        this.#cloneProgressReporter = candidate;
        return this.#cloneProgressReporter;
    }

    #disposeListeners(): void {
        if (!this.#listenerDisposers.length) {
            return;
        }
        for (const dispose of this.#listenerDisposers) {
            try {
                dispose();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('CloneManager', 'Clone listener dispose failed', runtimeError);
            }
        }
        this.#listenerDisposers = [];
    }

    #hasActiveCloneOperations(): boolean {
        return this.#cloneProgressReporter?.hasActiveOperations() === true;
    }

    #clearCloneModal(): void {
        this.#disposeListeners();
        this.#cloneProgressReporter?.destroy();
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const infoContainer = this.#host.view.optionalHTMLElement(modalUiSelector(this.modalId, 'plugin-info'), modalRoot);
        if (infoContainer) {
            infoContainer.replaceChildren();
        }
        const progressContainer = this.#host.view.optionalHTMLElement(modalUiSelector(this.modalId, 'progress-container'), modalRoot);
        if (progressContainer) {
            progressContainer.replaceChildren();
        }
        this.state.currentCloningPlugin = null;
        this.#cloneProgressReporter = null;
    }

    onModalClosed(): void {
        this.#disposeListeners();
        if (this.#hasActiveCloneOperations()) {
            return;
        }
        this.#clearCloneModal();
    }

    disposeForPageDestroy(): void {
        this.#clearCloneModal();
    }

    setCloneControlDisabled(element: Element, disabled: boolean): void {
        setElementDisabledState(this.#host.view, element, disabled, this.classNames.disabled);
    }

    openCloneModal = (plugin: PluginRecord): void => {
        if (!plugin?.name) {
            throw new Error('CloneManager requires a plugin with a name');
        }
        if (this.#host.policy.isPluginIncompatible(plugin)) {
            this.#host.policy.notifyPluginIncompatible(plugin);
            return;
        }
        if (!isPluginCloneSupported(plugin)) {
            this.#host.policy.showNotification(i18n.t('plugins.notifications.cloneNotSupported'), 'warning');
            return;
        }

        this.state.currentCloningPlugin = plugin;
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);

        const titleElement = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'title'), modalRoot);
        this.#host.view.updateText(
            titleElement,
            i18n.t('plugins.modal.clonePlugin.titleFormat', {
                plugin: this.#host.policy.formatPluginName(plugin.name)
            })
        );

        const pluginStatus = this.#host.policy.getPluginStatus(plugin);
        const displayName = resolvePluginDisplayName(plugin, this.#host.policy.formatPluginName);
        const infoContainer = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'plugin-info'), modalRoot);
        this.#host.view.updateHTML(
            infoContainer,
            renderClonePluginInfoMarkup({
                modalId: this.modalId,
                plugin,
                host: this.#host,
                security: this.security,
                pluginStatus,
                displayName
            })
        );

        const infoLed = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'info-led'), infoContainer);
        if (!(infoLed instanceof HTMLElement)) {
            throw new Error('CloneManager info LED must be an HTMLElement');
        }
        this.#host.policy.statusManager.updateIndicator(infoLed, pluginStatus);

        const customNameToggle = requireInputElement(this.#host.view, modalUiSelector(this.modalId, 'custom-name-toggle'), 'CloneManager custom name toggle', modalRoot);
        this.#disposeListeners();
        const dispose = this.#host.view.on(customNameToggle, 'change', (event: Event) => this.handleCloneCustomNameToggle(event));
        this.#listenerDisposers.push(dispose);

        this.resetCloneModalState();
        this.#host.view.modals.open(this.modalId);
    };

    resetCloneModalState(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const cloneModelsToggle = requireInputElement(this.#host.view, modalUiSelector(this.modalId, 'models-toggle'), 'CloneManager clone models toggle', modalRoot);
        const customNameToggle = requireInputElement(this.#host.view, modalUiSelector(this.modalId, 'custom-name-toggle'), 'CloneManager custom name toggle', modalRoot);
        const nameInput = requireInputElement(this.#host.view, modalUiSelector(this.modalId, 'name-input'), 'CloneManager name input', modalRoot);
        const nameInputContainer = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'name-input-container'), modalRoot);
        const startButton = requireButtonElement(this.#host.view, modalUiSelector(this.modalId, 'start'), 'CloneManager start button', modalRoot);
        const hasActiveCloneOperations = this.#hasActiveCloneOperations();

        cloneModelsToggle.checked = false;
        customNameToggle.checked = false;
        nameInput.value = '';

        this.#host.view.addClassName(nameInputContainer, this.classNames.hidden);
        this.setCloneControlDisabled(startButton, hasActiveCloneOperations);
        if (!hasActiveCloneOperations) {
            this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'progress-container'), modalRoot).replaceChildren();
        }
    }

    handleCloneCustomNameToggle(event: Event): void {
        if (!(event.target instanceof HTMLInputElement)) {
            throw new Error('CloneManager custom name toggle requires an input event target');
        }
        const isChecked = event.target.checked === true;
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const nameInputContainer = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'name-input-container'), modalRoot);
        this.#host.view.toggleClassName(nameInputContainer, this.classNames.hidden, !isChecked);
        if (isChecked) {
            requireInputElement(this.#host.view, modalUiSelector(this.modalId, 'name-input'), 'CloneManager name input', modalRoot).focus();
        }
    }

    async handleStartClone(): Promise<void> {
        const plugin = this.state.currentCloningPlugin;
        if (!plugin) {
            throw new Error('CloneManager requires an active cloning plugin');
        }

        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const cloneModelsToggle = requireInputElement(this.#host.view, modalUiSelector(this.modalId, 'models-toggle'), 'CloneManager clone models toggle', modalRoot);
        const customNameToggle = requireInputElement(this.#host.view, modalUiSelector(this.modalId, 'custom-name-toggle'), 'CloneManager custom name toggle', modalRoot);
        const nameInput = requireInputElement(this.#host.view, modalUiSelector(this.modalId, 'name-input'), 'CloneManager name input', modalRoot);

        const cloneModels = cloneModelsToggle.checked === true;
        const useCustomName = customNameToggle.checked === true;
        const targetName = resolveCloneTargetName(useCustomName, nameInput.value);

        if (useCustomName && targetName !== null && !isValidCloneTargetName(targetName)) {
            this.#host.policy.showNotification(i18n.t('plugins.notifications.cloneInvalidName'), 'warning');
            return;
        }

        await this.startPluginClone(plugin, { cloneModels, targetName });
    }

    async startPluginClone(plugin: PluginRecord, cloneOptions: CloneOptions = {}): Promise<void> {
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const startButton = requireButtonElement(this.#host.view, modalUiSelector(this.modalId, 'start'), 'CloneManager start button', modalRoot);
        await executePluginCloneAction({
            host: this.#host,
            plugin,
            cloneOptions,
            modalId: this.modalId,
            startButton,
            setCloneControlDisabled: (element: Element, disabled: boolean) => this.setCloneControlDisabled(element, disabled),
            requireCloneProgressReporter: () => this.#requireCloneProgressReporter()
        });
    }
}

export { CloneModalManager };
