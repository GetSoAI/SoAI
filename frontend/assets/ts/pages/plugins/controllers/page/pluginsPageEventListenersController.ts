/* SoAI - Plugins page event listeners controller [frontend/assets/ts/pages/plugins/controllers/page/pluginsPageEventListenersController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { shouldPreventDefaultExceptFileActionElement } from '@core/dom/dataAction.ts';
import { bindMultiRootPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { bindManagedModalLifecycleEvents, createManagedModalCloseBinding } from '@core/modals/managedModalLifecycle.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { CLONE_PLUGIN_MODAL_ID, CONCURRENT_PLUGINS_MODAL_ID, DOWNLOAD_PLUGIN_MODAL_ID, MANAGE_BACKEND_MODAL_ID, PLUGIN_CONFIG_MODAL_ID, PLUGIN_INFO_MODAL_ID, type CloneModalManager, type ConcurrentModalManager, type ConfigManager, type InfoManager, type ManageBackendModalManager, type PluginDownloadModalManager } from '@features/plugins/public.ts';
import type { PluginsInteractionController } from '@pages/plugins/controllers/interactionController.ts';
import { isPluginsActionId } from '@pages/plugins/actions.ts';

type PluginsModalLifecycleManagers = {
    downloadModalManager: PluginDownloadModalManager;
    configManager: ConfigManager;
    manageBackendModalManager: ManageBackendModalManager;
    infoManager: InfoManager;
    cloneManager: CloneModalManager;
    concurrentManager: ConcurrentModalManager;
};

type PluginsPageEventListenerDependencies = {
    signal: AbortSignal;
    interactionController: PluginsInteractionController;
    modalCloseDependencies: PluginsModalLifecycleManagers;
};

const bindPluginsPageModalEventListeners = (dependencies: PluginsPageEventListenerDependencies): void => {
    const { signal } = dependencies;
    const modalPresenter = requireModalPresenter();
    const actionModalRoots: readonly HTMLElement[] = [modalPresenter.requireElement(DOWNLOAD_PLUGIN_MODAL_ID), modalPresenter.requireElement(PLUGIN_CONFIG_MODAL_ID), modalPresenter.requireElement(MANAGE_BACKEND_MODAL_ID), modalPresenter.requireElement(PLUGIN_INFO_MODAL_ID), modalPresenter.requireElement(CLONE_PLUGIN_MODAL_ID), modalPresenter.requireElement(CONCURRENT_PLUGINS_MODAL_ID)];

    bindManagedModalLifecycleEvents({
        signal,
        resolveModalElement: (modalId) => modalPresenter.requireElement(modalId),
        bindings: [createManagedModalCloseBinding(DOWNLOAD_PLUGIN_MODAL_ID, dependencies.modalCloseDependencies.downloadModalManager), createManagedModalCloseBinding(PLUGIN_CONFIG_MODAL_ID, dependencies.modalCloseDependencies.configManager), createManagedModalCloseBinding(MANAGE_BACKEND_MODAL_ID, dependencies.modalCloseDependencies.manageBackendModalManager), createManagedModalCloseBinding(PLUGIN_INFO_MODAL_ID, dependencies.modalCloseDependencies.infoManager), createManagedModalCloseBinding(CLONE_PLUGIN_MODAL_ID, dependencies.modalCloseDependencies.cloneManager), createManagedModalCloseBinding(CONCURRENT_PLUGINS_MODAL_ID, dependencies.modalCloseDependencies.concurrentManager)]
    });

    bindMultiRootPageActionDispatcher({
        roots: actionModalRoots,
        signal,
        label: 'PluginsPage modal',
        isAction: isPluginsActionId,
        events: {
            click: {
                preventDefault: 'never',
                mouseButton: 'primary',
                ignoreDisabled: true,
                onAction: ({ event, action, actionElement }): void => {
                    const handled = dependencies.interactionController.handlePageActionEvent(event, action, actionElement);
                    if (!handled) {
                        return;
                    }
                    if (shouldPreventDefaultExceptFileActionElement(actionElement)) {
                        event.preventDefault();
                    }
                    event.stopPropagation();
                }
            },
            change: {
                preventDefault: 'never',
                mouseButton: 'primary',
                ignoreDisabled: true,
                onAction: ({ event, action, actionElement }): void => {
                    dependencies.interactionController.handlePageActionEvent(event, action, actionElement);
                }
            },
            input: {
                preventDefault: 'never',
                mouseButton: 'primary',
                ignoreDisabled: true,
                onAction: ({ event, action, actionElement }): void => {
                    dependencies.interactionController.handlePageActionEvent(event, action, actionElement);
                }
            }
        }
    });
};

export { bindPluginsPageModalEventListeners };
