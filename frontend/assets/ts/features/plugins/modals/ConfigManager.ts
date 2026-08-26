/* SoAI - Plugin configuration modal manager [frontend/assets/ts/features/plugins/modals/ConfigManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { SaveController } from '@core/save/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { validateClassNames } from '@core/ui/classNames.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { loadPluginConfigModalContext } from '@features/plugins/modals/config/loadContext.ts';
import { PLUGIN_CONFIG_MODAL_ID } from '@features/plugins/modals/pluginConfigModal.ts';
import { clearPluginConfigFormIfPresent, disposeConfigDisposer, disposeConfigDisposers, focusFirstPluginConfigField } from '@features/plugins/modals/config/effects.ts';
import { bindPluginConfigModalListeners, initializePluginConfigChangeTracker } from '@features/plugins/modals/config/operations.ts';
import { createPluginConfigModalSaveController } from '@features/plugins/modals/config/saveController.ts';
import { savePluginConfigFlow } from '@features/plugins/modals/config/saveFlow.ts';
import type { ConfigManagerHost, ConfigManagerOptions, ConfigState, ConfigurationManager } from '@features/plugins/modals/config/types.ts';
import { renderConfigEmptyMarkup, renderConfigGridMarkup, renderConfigLoadingMarkup } from '@features/plugins/modals/config/view.ts';

class ConfigManager {
    readonly modalId = PLUGIN_CONFIG_MODAL_ID;
    readonly #host: ConfigManagerHost;
    private classNames: Pick<Required<ConfigManagerOptions['classNames']>, 'disabled'>;
    private security: ConfigManagerOptions['security'];
    state: ConfigState;
    #save: SaveController | null = null;
    #saveButton: HTMLButtonElement | null = null;
    #configurationManager: ConfigurationManager | null = null;
    #configurationManagerChangeDisposer: (() => void) | null = null;
    #changeTracker: FieldStateTracker | null = null;
    #formListenerDisposers: Array<() => void> = [];
    #prepareSequence = 0;
    #focusTimerId: number | null = null;

    constructor({ host, classNames, security }: ConfigManagerOptions) {
        if (!host) {
            throw new Error('ConfigManager requires a host');
        }
        this.#host = host;
        this.state = { configuringPlugin: null };
        this.classNames = validateClassNames(classNames, ['disabled'], 'ConfigManager');
        if (!security) {
            throw new Error('ConfigManager requires a security module');
        }
        this.security = security;
    }

    #requireConfigurationManager(): ConfigurationManager {
        if (!this.#configurationManager) {
            throw new Error('ConfigManager requires a configuration manager');
        }
        return this.#configurationManager;
    }

    #requireChangeTracker(): FieldStateTracker {
        if (!this.#changeTracker) {
            throw new Error('ConfigManager requires a change tracker');
        }
        return this.#changeTracker;
    }

    handleSavePluginConfig(): void {
        void this.#save?.requestSave();
    }

    #clearModalState(): void {
        const modalRoot = this.#host.modals.requireElement(this.modalId);
        this.#prepareSequence += 1;
        this.#host.clearTimer(this.#focusTimerId);
        this.#focusTimerId = null;
        this.#disposeFormListeners();
        this.#disposeConfigurationManagerChangeListener();
        clearPluginConfigFormIfPresent(this.#host, this.modalId, modalRoot);
        this.state.configuringPlugin = null;
        this.#changeTracker?.clearAll();
        this.#configurationManager = null;
        this.#changeTracker = null;
        this.#save?.dispose();
        this.#save = null;
        this.#saveButton = null;
    }

    onModalClosed(): void {
        this.#clearModalState();
    }

    disposeForPageDestroy(): void {
        this.#clearModalState();
    }

    prepareConfigModal = (plugin: PluginRecord): void => {
        void this.#prepareConfigModal(plugin).catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.error('ConfigManager', i18n.t('plugins.modal.config.loadFailed'), runtimeError);
            this.#host.showNotification(i18n.t('plugins.modal.config.loadFailed'), 'error');
        });
    };

    async #prepareConfigModal(plugin: PluginRecord): Promise<void> {
        if (!plugin?.name) {
            throw new Error('ConfigManager requires a plugin with a name');
        }

        const prepareSequence = this.#prepareSequence + 1;
        this.#prepareSequence = prepareSequence;

        const modalRoot = this.#host.modals.requireElement(this.modalId);
        const contentTitle = this.#host.requireHTMLElement(modalUiSelector(this.modalId, 'content-title'), modalRoot);
        this.#host.updateText(contentTitle, i18n.t('plugins.modal.config.contentTitleFormat', { plugin: plugin.name }));
        const form = this.#host.requireHTMLElement(modalUiSelector(this.modalId, 'form'), modalRoot);
        this.state.configuringPlugin = plugin;
        this.#changeTracker?.clearAll();
        this.#changeTracker = null;

        this.#disposeConfigurationManagerChangeListener();
        this.#disposeFormListeners();

        this.#host.updateHTML(form, renderConfigLoadingMarkup());
        setAriaBusy(modalRoot, true);
        this.#host.modals.open(this.modalId);
        const saveButtonCandidate = this.#host.requireHTMLElement(modalUiSelector(this.modalId, 'save'), modalRoot);
        if (!(saveButtonCandidate instanceof HTMLButtonElement)) {
            throw new TypeError('Plugin config save button must be an HTMLButtonElement');
        }
        this.#saveButton = saveButtonCandidate;
        this.#save?.dispose();
        this.#save = createPluginConfigModalSaveController({
            hasChanges: (): boolean => Boolean(this.#changeTracker?.hasPendingChanges() || this.#configurationManager?.hasChanges),
            isValid: (): boolean => this.#changeTracker?.isValid() ?? true,
            save: async (): Promise<void> => this.savePluginConfig()
        });
        this.#save.attach({
            resolveSaveButtons: (): readonly HTMLButtonElement[] => {
                const button = this.#saveButton;
                return button ? [button] : [];
            },
            busyRoots: [modalRoot],
            autoNotifyRoot: form,
            buttonDisabledClassName: this.classNames.disabled
        });

        const loadContext = await loadPluginConfigModalContext({
            host: this.#host,
            plugin
        });
        const { config, gpuBindingState, hideGpuBindingField } = loadContext;

        if (prepareSequence !== this.#prepareSequence) {
            return;
        }

        setAriaBusy(modalRoot, false);
        if (!config) {
            this.#host.updateHTML(form, renderConfigEmptyMarkup(this.security, { gpuBindingState: null, hideGpuBindingField }));
            this.updatePluginConfigSaveButton();
            return;
        }

        this.#host.updateHTML(form, renderConfigGridMarkup(config, this.security, { gpuBindingState, hideGpuBindingField }));

        this.#configurationManager = this.#host.createConfigurationManager();
        this.#configurationManager.initialize(config);
        this.#configurationManagerChangeDisposer = this.#configurationManager.onChange(() => this.updatePluginConfigSaveButton());

        this.initializePluginConfigChangeTracker(config);
        this.#formListenerDisposers = bindPluginConfigModalListeners({
            host: this.#host,
            form,
            security: this.security,
            manager: this.#configurationManager,
            gpuBindingState,
            onFieldValueChanged: (key: string) => this.updateConfigFieldModifiedState(key),
            onFieldValidationChanged: (key: string, message: string | null) => {
                this.updateConfigFieldValidationState(key, message);
            }
        });
        this.updatePluginConfigSaveButton();

        this.#host.clearTimer(this.#focusTimerId);
        this.#focusTimerId = this.#host.setTimeout(() => {
            if (prepareSequence !== this.#prepareSequence) {
                return;
            }
            focusFirstPluginConfigField(this.#host, form);
        }, 0);
    }

    #disposeFormListeners(): void {
        this.#formListenerDisposers = disposeConfigDisposers(this.#formListenerDisposers, 'Config form listener dispose failed');
    }

    #disposeConfigurationManagerChangeListener(): void {
        this.#configurationManagerChangeDisposer = disposeConfigDisposer(this.#configurationManagerChangeDisposer, 'Config manager change-listener dispose failed');
    }

    initializePluginConfigChangeTracker(config: JsonObject): void {
        const manager = this.#requireConfigurationManager();
        const modalRoot = this.#host.modals.requireElement(this.modalId);
        const form = this.#host.requireHTMLElement(modalUiSelector(this.modalId, 'form'), modalRoot);
        this.#changeTracker = initializePluginConfigChangeTracker({
            host: this.#host,
            form,
            manager,
            config
        });
    }

    updateConfigFieldModifiedState(key: string): void {
        if (!key) {
            throw new Error('ConfigManager requires a config key');
        }
        this.#requireChangeTracker().update(key);
    }

    updateConfigFieldValidationState(key: string, message: string | null): void {
        if (!key) {
            throw new Error('ConfigManager requires a config key');
        }
        this.#requireChangeTracker().setInvalid(key, message);
        this.updatePluginConfigSaveButton();
    }

    updatePluginConfigSaveButton(): void {
        this.#save?.notifyChanged();
    }

    async savePluginConfig(): Promise<void> {
        if (!this.state.configuringPlugin || !this.#configurationManager) {
            throw new Error('ConfigManager save requires an active plugin and configuration manager');
        }
        if (!this.#requireChangeTracker().isValid()) {
            throw new Error(i18n.t('plugins.modal.config.fixInvalidFields'));
        }

        const activePluginName = this.state.configuringPlugin.name;
        const activeConfigurationManager = this.#configurationManager;
        const activePrepareSequence = this.#prepareSequence;

        if (!activePluginName) {
            throw new Error('ConfigManager save requires a plugin name');
        }

        const isActiveSaveContext = (): boolean => {
            return activePrepareSequence === this.#prepareSequence && this.#configurationManager === activeConfigurationManager && this.state.configuringPlugin?.name === activePluginName;
        };

        await savePluginConfigFlow({
            host: this.#host,
            modalId: this.modalId,
            pluginName: activePluginName,
            configurationManager: activeConfigurationManager,
            isActiveSaveContext,
            clearModifiedStates: () => this.clearAllPluginConfigModifiedStates(),
            onFinalize: () => this.updatePluginConfigSaveButton()
        });
    }

    clearAllPluginConfigModifiedStates(): void {
        this.#requireChangeTracker().clearAll();
        this.updatePluginConfigSaveButton();
    }
}

export { ConfigManager };
