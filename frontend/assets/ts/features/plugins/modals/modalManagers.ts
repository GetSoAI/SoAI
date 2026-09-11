/* SoAI - Plugin modal manager registry [frontend/assets/ts/features/plugins/modals/modalManagers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StatusManager } from '@core/state/statusmanager/service.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { C_DISABLED, C_HIDDEN, CONCURRENT_PLUGINS_SLIDER } from '@features/plugins/contracts/pluginPageSupport.ts';
import { ManageBackendModalManager } from '@features/plugins/modals/backend/managebackendmodal/service.ts';
import { CloneModalManager } from '@features/plugins/modals/CloneModalManager.ts';
import type { ConcurrentManagerHost } from '@features/plugins/modals/concurrentmanager/types.ts';
import { ConcurrentModalManager } from '@features/plugins/modals/ConcurrentModalManager.ts';
import type { ConfigManagerHost } from '@features/plugins/modals/config/types.ts';
import { ConfigManager } from '@features/plugins/modals/ConfigManager.ts';
import { PluginDownloadModalManager, type DownloadManagerHost } from '@features/plugins/modals/downloadmanager/service.ts';
import { InfoManager, type InfoManagerHost } from '@features/plugins/modals/InfoManager.ts';
import type { PluginsModalManagers, PluginsModalManagersDependencies } from '@features/plugins/modals/modalManagerContracts.ts';

const createPluginsModalManagers = (dependencies: PluginsModalManagersDependencies): PluginsModalManagers => {
    const { foundation, concurrency, operations, presentation, state, updates, progress } = dependencies;
    if (!foundation.statusManager) {
        throw new Error('Plugins modal managers require a status manager');
    }
    const callbacks = foundation.callbacks;
    const downloadManagerHost: DownloadManagerHost = {
        view: {
            modals: callbacks.modals,
            requireHTMLElement: callbacks.requireHTMLElement,
            optionalHTMLElement: callbacks.optionalHTMLElement,
            updateText: callbacks.updateText,
            updateHTML: callbacks.updateHTML,
            addClassName: callbacks.addClassName,
            removeClassName: callbacks.removeClassName,
            setUIValue: callbacks.setUIValue,
            updateProperty: callbacks.updateProperty,
            updateAttribute: callbacks.updateAttribute,
            toggleClassName: callbacks.toggleClassName
        },
        execution: {
            streams: foundation.streams,
            cancelDownload: operations.cancelDownload,
            createStreamHandlers: (key: string, message: string, streamCallbacks: Parameters<DownloadManagerHost['execution']['createStreamHandlers']>[2]) => operations.createStreamHandlers(key, message, streamCallbacks),
            trackAcceptedTask: (taskId: string, options: Parameters<DownloadManagerHost['execution']['trackAcceptedTask']>[1]) => operations.trackAcceptedTask(taskId, options),
            startTaskAction: (url: string, options: Parameters<DownloadManagerHost['execution']['startTaskAction']>[1]) => operations.startTaskAction(url, options),
            api: foundation.api,
            createOperationProgressReporter: operations.createOperationProgressReporter
        },
        session: {
            hasClipboardSupport: operations.hasClipboardSupport,
            copyToClipboard: callbacks.copyToClipboard,
            showNotification: callbacks.showNotification,
            sanitizeHtml: (value: string): string => foundation.security.escapeHtml(value),
            isAdmin: operations.isAdmin,
            setLocationHash: operations.setLocationHash
        }
    };

    const configManagerHost: ConfigManagerHost = {
        modals: callbacks.modals,
        requireHTMLElement: callbacks.requireHTMLElement,
        optionalHTMLElement: callbacks.optionalHTMLElement,
        queryUI: callbacks.queryUI,
        showNotification: callbacks.showNotification,
        on: callbacks.on,
        updateHTML: callbacks.updateHTML,
        updateText: callbacks.updateText,
        updateProperty: callbacks.updateProperty,
        toggleClassName: callbacks.toggleClassName,
        setTimeout: callbacks.setTimeout,
        clearTimer: callbacks.clearTimer,
        createConfigurationManager: callbacks.createConfigurationManager,
        api: {
            configs: {
                get: (name: string) => foundation.api.configs.get(name),
                update: (name: string, data: JsonObject) => foundation.api.configs.update(name, data)
            },
            hardware: {
                snapshot: (options) => foundation.api.hardware.snapshot(options)
            }
        }
    };

    const infoManagerHost: InfoManagerHost = {
        modals: callbacks.modals,
        requireHTMLElement: callbacks.requireHTMLElement,
        optionalHTMLElement: callbacks.optionalHTMLElement,
        updateHTML: callbacks.updateHTML,
        copyToClipboard: callbacks.copyToClipboard,
        hasClipboardSupport: operations.hasClipboardSupport,
        showNotification: (message, type): void => callbacks.showNotification(message, type),
        sanitizeText: callbacks.sanitizeText,
        sanitizeClassName: callbacks.sanitizeClassName
    };

    const concurrentManagerHost: ConcurrentManagerHost = {
        view: {
            modals: callbacks.modals,
            requireHTMLElement: callbacks.requireHTMLElement,
            updateProperty: callbacks.updateProperty,
            updateAttribute: callbacks.updateAttribute,
            addClassName: callbacks.addClassName,
            removeClassName: callbacks.removeClassName,
            updateText: callbacks.updateText,
            toggleClassName: callbacks.toggleClassName,
            optionalHTMLElement: callbacks.optionalHTMLElement,
            showNotification: callbacks.showNotification,
            on: callbacks.on
        },
        state: {
            getMaxConcurrentPlugins: concurrency.getMaxConcurrentPlugins,
            setMaxConcurrentPlugins: concurrency.setMaxConcurrentPlugins,
            getConcurrentPluginsOriginalValue: concurrency.getConcurrentPluginsOriginalValue,
            setConcurrentPluginsOriginalValue: concurrency.setConcurrentPluginsOriginalValue,
            getCoreConfigCache: concurrency.getCoreConfigCache,
            setCoreConfigCache: concurrency.setCoreConfigCache,
            updateStats: operations.updateStats
        },
        operations: {
            loadCoreConfig: operations.loadCoreConfig,
            getRestartOverlay: concurrency.getRestartOverlay,
            api: {
                configs: {
                    update: (name: string, config: JsonObject) => {
                        if (!isJsonObject(config)) {
                            throw new TypeError('Concurrent plugins config update requires an object payload');
                        }
                        return foundation.api.configs.update(name, config);
                    }
                },
                ...(foundation.api.system ? { system: foundation.api.system } : {})
            }
        }
    };

    const backendClassNames = { hidden: C_HIDDEN, disabled: C_DISABLED };
    const manageBackendModalManager = new ManageBackendModalManager({
        host: {
            view: {
                modals: callbacks.modals,
                requireHTMLElement: callbacks.requireHTMLElement,
                optionalHTMLElement: callbacks.optionalHTMLElement,
                on: callbacks.on,
                updateText: callbacks.updateText,
                updateHTML: callbacks.updateHTML,
                updateProperty: callbacks.updateProperty,
                updateAttribute: callbacks.updateAttribute,
                addClassName: callbacks.addClassName,
                removeClassName: callbacks.removeClassName,
                toggleClassName: callbacks.toggleClassName,
                setDataAttribute: callbacks.setDataAttribute,
                dom: foundation.dom
            },
            policy: {
                checkBackendInstallationSupport: presentation.checkBackendInstallationSupport,
                isPluginPermanentlyDisabled: presentation.isPluginPermanentlyDisabled,
                notifyPluginIncompatible: presentation.notifyPluginIncompatible
            },
            status: {
                getBackendStatus: presentation.getBackendStatus,
                getBackendVersion: presentation.getBackendVersion,
                getPluginStatus: presentation.getPluginStatus,
                handleBackendWebsiteLinkClick: presentation.handleBackendWebsiteLinkClick,
                getStatusManager: (): StatusManager | null => foundation.statusManager,
                subscribeModalLedUpdates: state.subscribeModalLedUpdates,
                unsubscribeModalLedUpdates: state.unsubscribeModalLedUpdates,
                setCurrentManagingPlugin: state.setCurrentManagingPlugin,
                setCurrentUpdateInfo: state.setCurrentUpdateInfo,
                normalizeVersion: updates.normalizeVersion
            },
            operations: {
                checkUpdates: updates.checkUpdates,
                getBackendVariants: updates.getBackendVariants,
                saveBackendVariantSelection: updates.saveBackendVariantSelection,
                streams: foundation.streams,
                createStreamHandlers: (key, message, streamCallbacks) => operations.createStreamHandlers(key, message, streamCallbacks),
                startTaskAction: (endpoint, options, runtimeOptions) => operations.startTaskAction(endpoint, options, runtimeOptions),
                startTaskCommand: (command, options, runtimeOptions) => operations.startTaskCommand(command, options, runtimeOptions),
                beginOptimisticOperation: operations.beginOptimisticOperation,
                formatPluginName: presentation.formatPluginName,
                showNotification: callbacks.showNotification
            }
        },
        classNames: backendClassNames,
        security: foundation.security
    });

    const cloneManager = new CloneModalManager({
        host: {
            view: {
                modals: callbacks.modals,
                requireHTMLElement: callbacks.requireHTMLElement,
                optionalHTMLElement: callbacks.optionalHTMLElement,
                updateText: callbacks.updateText,
                updateHTML: callbacks.updateHTML,
                addClassName: callbacks.addClassName,
                toggleClassName: callbacks.toggleClassName,
                updateProperty: callbacks.updateProperty,
                on: callbacks.on
            },
            policy: {
                formatPluginName: presentation.formatPluginName,
                getPluginStatus: presentation.getPluginStatus,
                sanitizeText: callbacks.sanitizeText,
                statusManager: foundation.statusManager,
                isPluginIncompatible: progress.isPluginIncompatible,
                notifyPluginIncompatible: presentation.notifyPluginIncompatible,
                showNotification: callbacks.showNotification
            },
            execution: {
                setPluginProgressMeta: progress.setPluginProgressMeta,
                createStreamHandlers: (key, message, streamCallbacks) => operations.createStreamHandlers(key, message, streamCallbacks),
                startTaskAction: (endpoint, options) => operations.startTaskAction(endpoint, options),
                streams: foundation.streams,
                consumePluginProgressMeta: progress.consumePluginProgressMeta,
                createOperationProgressReporter: (containerId, options) => {
                    const reporterOptions = {
                        ...(options.onCancel ? { onCancel: options.onCancel } : {}),
                        ...(options.backgroundButtonId === undefined ? {} : { backgroundButtonId: options.backgroundButtonId })
                    };
                    const reporter = operations.createOperationProgressReporter(containerId, reporterOptions);
                    return typeof reporter === 'object' && reporter !== null ? reporter : null;
                }
            }
        },
        classNames: backendClassNames,
        security: foundation.security
    });

    return {
        downloadModalManager: new PluginDownloadModalManager({
            host: downloadManagerHost,
            classNames: { disabled: C_DISABLED, hidden: C_HIDDEN, active: 'is-active' }
        }),
        configManager: new ConfigManager({
            host: configManagerHost,
            classNames: { disabled: C_DISABLED },
            security: foundation.security
        }),
        infoManager: new InfoManager({ host: infoManagerHost, security: foundation.security, getCapabilityDescriptors: presentation.getCapabilityDescriptors }),
        concurrentManager: new ConcurrentModalManager({
            host: concurrentManagerHost,
            classNames: { disabled: C_DISABLED, hidden: C_HIDDEN },
            sliderBounds: {
                min: CONCURRENT_PLUGINS_SLIDER.MIN,
                defaultMax: CONCURRENT_PLUGINS_SLIDER.DEFAULT_MAX,
                maxLimit: CONCURRENT_PLUGINS_SLIDER.MAX_LIMIT
            }
        }),
        manageBackendModalManager,
        cloneManager
    };
};
export { createPluginsModalManagers };
export type { PluginsModalManagers, PluginsModalManagersDependencies };
