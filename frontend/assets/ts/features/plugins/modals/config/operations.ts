/* SoAI - Plugin configuration modal operations [frontend/assets/ts/features/plugins/modals/config/operations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { type JsonValue, isJsonValue, type JsonObject } from '@core/types/jsonValues.ts';
import { bindPluginConfigInputListeners } from '@features/plugins/modals/config/effects.ts';
import { bindPluginGpuBindingSelectorListeners } from '@features/plugins/modals/config/gpuBindingSelector.ts';
import { PLUGIN_GPU_BINDING_KEY, type PluginGpuBindingSelectorState } from '@features/plugins/modals/config/gpuBindingTypes.ts';
import { collectConfigFieldElements, collectPluginGpuBindingFieldElements, normalizePluginConfigPayload } from '@features/plugins/modals/config/service.ts';
import type { ConfigManagerHost, ConfigurationManager, SecurityService } from '@features/plugins/modals/config/types.ts';

interface LoadPluginConfigContext {
    host: ConfigManagerHost;
    pluginName: string;
}

interface InitializePluginConfigChangeTrackerContext {
    host: ConfigManagerHost;
    form: HTMLElement;
    manager: ConfigurationManager;
    config: JsonObject;
}

interface BindPluginConfigModalListenersContext {
    host: ConfigManagerHost;
    form: HTMLElement;
    security: SecurityService;
    manager: ConfigurationManager;
    gpuBindingState: PluginGpuBindingSelectorState | null;
    onFieldValueChanged: (key: string) => void;
    onFieldValidationChanged: (key: string, message: string | null, validationId: string | null) => void;
}

interface SavePluginConfigChangesContext {
    host: ConfigManagerHost;
    modalId: string;
    pluginName: string;
    configurationManager: ConfigurationManager;
    isActiveSaveContext: () => boolean;
    clearModifiedStates: () => void;
}

const loadPluginConfig = async (context: LoadPluginConfigContext): Promise<JsonObject | null> => {
    try {
        const candidate = await context.host.api.configs.get(context.pluginName);
        return normalizePluginConfigPayload(candidate);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ConfigManager', i18n.t('plugins.modal.config.loadFailed'), runtimeError);
        context.host.showNotification(i18n.t('plugins.modal.config.loadFailed'), 'error');
        return null;
    }
};

const initializePluginConfigChangeTracker = (context: InitializePluginConfigChangeTrackerContext): FieldStateTracker => {
    const fieldElements = collectConfigFieldElements(context.host, context.form);
    const resolveFieldElements = (key: string): Element[] => {
        if (!key) {
            return [];
        }
        if (key === PLUGIN_GPU_BINDING_KEY) {
            return collectPluginGpuBindingFieldElements(context.host, context.form);
        }
        const element = fieldElements.get(key);
        return element ? [element] : [];
    };
    const resolveFieldElement = (key: string): Element | null => resolveFieldElements(key)[0] ?? null;

    const tracker = new FieldStateTracker({
        getElement: resolveFieldElement,
        getElements: resolveFieldElements,
        getCurrentValue: (key: string) => context.manager.getValue(key),
        getOriginalValue: (key: string) => context.manager.getValueByPath(context.manager.originalData, key),
        comparator: (current: JsonValue | null | undefined, original: JsonValue | null | undefined) => {
            if (!isJsonValue(current) || !isJsonValue(original)) {
                return current === original;
            }
            return context.manager.areValuesEqual(current, original);
        }
    });

    for (const key of Object.keys(context.config)) {
        tracker.update(key);
    }

    return tracker;
};

const bindPluginConfigModalListeners = (context: BindPluginConfigModalListenersContext): Array<() => void> => {
    return [
        ...bindPluginConfigInputListeners({
            host: context.host,
            form: context.form,
            manager: context.manager,
            onFieldValueChanged: context.onFieldValueChanged,
            onFieldValidationChanged: context.onFieldValidationChanged
        }),
        ...bindPluginGpuBindingSelectorListeners({
            host: context.host,
            form: context.form,
            security: context.security,
            state: context.gpuBindingState,
            manager: context.manager,
            onValueChanged: context.onFieldValueChanged
        })
    ];
};

const savePluginConfigChanges = async (context: SavePluginConfigChangesContext): Promise<void> => {
    try {
        await context.host.api.configs.update(context.pluginName, context.configurationManager.currentData);
    } catch (error) {
        const runtimeError = ensureError(error);
        throw runtimeError;
    }

    if (!context.isActiveSaveContext()) {
        return;
    }

    context.configurationManager.commitChanges();
    context.clearModifiedStates();
    context.host.showNotification(i18n.t('plugins.notifications.configSaveSuccess', { plugin: context.pluginName }), 'success');
    context.host.modals.close(context.modalId);
};

export { bindPluginConfigModalListeners, initializePluginConfigChangeTracker, loadPluginConfig, savePluginConfigChanges };
