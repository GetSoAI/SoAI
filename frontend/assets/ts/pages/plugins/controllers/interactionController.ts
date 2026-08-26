/* SoAI - Plugins page interaction controller [frontend/assets/ts/pages/plugins/controllers/interactionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createCardActionDispatcher } from '@core/dom/cardActionDispatcher.ts';
import { shouldPreventDefaultExceptFileActionElement } from '@core/dom/dataAction.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isActionToggleInteractionDisabled } from '@core/toggleSwitch.ts';
import type { CardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { isPluginRecord } from '@core/types/pluginRecordGuards.ts';
import { METRIC_BADGE_HANDLERS, PLUGINS_ACTION_METRIC_BADGE, PLUGINS_ACTION_TOGGLE_ENABLED, PLUGIN_ACTION_HANDLERS, type PluginActionHost } from '@features/plugins/public.ts';
import type { PluginsActionId, PluginsCardActionId } from '@pages/plugins/actions.ts';
import { dispatchPluginsPageAction } from '@pages/plugins/controllers/pluginsPageActionDispatch.ts';
import { PLUGIN_CARD_SELECTOR } from '@pages/plugins/controllers/pluginsPageRuntimeSupport.ts';
import { navigateFromPluginsMetricBadge, resolvePluginsMetricBadgeType } from '@pages/plugins/widgets/pluginsMetricBadges.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

const PLUGIN_ACTION_ITEM_SELECTOR = `${PLUGIN_CARD_SELECTOR}, .plugins-list-row`;

const isDisabledPluginToggleAction = (action: string, actionElement: Element): boolean => {
    return action === PLUGINS_ACTION_TOGGLE_ENABLED && isActionToggleInteractionDisabled(actionElement);
};

interface PluginsInteractionControllerDependencies extends PageDomOwnerHost, PageFeedbackOwnerHost {
    getCardController(): CardPageController | null;
    pluginActionHost: PluginActionHost;
    getRouter(): Router | null;
    getDownloadModalManager(): {
        openDownloadPluginModal(): void;
        handleChooseFileClick(): void;
        handleConfirmPluginDownload(): void;
        handleUrlTabClick(): void;
        handleFileTabClick(): void;
        handleManualPluginTabClick(): void;
        handleManualPluginPathCopy(): void;
        handleManualPluginOpenFileExplorer(): void;
        handleManualPluginPowerClick(): void;
        handlePluginUrlInput(event: Event): void;
        handlePluginFileChange(event: Event): void;
    };
    getConcurrentManager(): {
        openConcurrentPluginsModal(): void;
        handleSaveConcurrentPlugins(): void;
        handleConcurrentPluginsSliderInput(event: Event): void;
        handleConcurrentPluginsInputChange(event: Event): void;
    };
    getConfigManager(): { handleSavePluginConfig(): void };
    copyPluginInfo(): Promise<void>;
    getManageBackendModalManager(): {
        handleStartBackendInstall(): void;
        handleCheckBackendUpdate(): Promise<void>;
        handleUninstallBackend(): Promise<void>;
    };
    getCloneManager(): { handleStartClone(): Promise<void> };
    handleStopAllPlugins(): Promise<void>;
    handleToggleViewMode(): void;
    handleSortList(actionElement: Element): void;
}

class PluginsInteractionController {
    readonly #dependencies: PluginsInteractionControllerDependencies;

    constructor(dependencies: PluginsInteractionControllerDependencies) {
        this.#dependencies = dependencies;
    }

    handleCardActionClick(event: Event, actionElement: Element, action: PluginsCardActionId): void {
        const cardController = this.#dependencies.getCardController();
        if (!cardController) {
            throw new Error('PluginsPage card controller is required for card action clicks');
        }
        const dispatch = createCardActionDispatcher({
            cardSelector: PLUGIN_ACTION_ITEM_SELECTOR,
            context: 'Plugin card action',
            resolveItem: (card) => {
                const pluginCandidate = cardController.getItemFromCard(card);
                if (!isPluginRecord(pluginCandidate)) {
                    return null;
                }
                return pluginCandidate;
            },
            onAction: ({ action: actionId, actionElement: resolvedActionElement, item }): void => {
                if (actionId === PLUGINS_ACTION_TOGGLE_ENABLED) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                if (isDisabledPluginToggleAction(actionId, resolvedActionElement)) {
                    return;
                }
                if (shouldPreventDefaultExceptFileActionElement(resolvedActionElement)) {
                    event.preventDefault();
                }
                event.stopPropagation();
                const handler = PLUGIN_ACTION_HANDLERS[actionId];
                if (!handler) {
                    throw new Error(`Plugin action handler is unavailable: ${String(actionId)}`);
                }
                handler(this.#dependencies.pluginActionHost, item, event);
            }
        });
        if (!(actionElement instanceof HTMLElement)) {
            throw new Error('Plugin card action requires an HTMLElement action element');
        }
        dispatch({ event, action, actionElement });
    }

    handlePageActionEvent(event: Event, action: PluginsActionId, actionElement: Element): boolean {
        const downloadModalManager = this.#dependencies.getDownloadModalManager();
        const concurrentManager = this.#dependencies.getConcurrentManager();
        const manageBackendModalManager = this.#dependencies.getManageBackendModalManager();
        return dispatchPluginsPageAction(
            {
                modal: {
                    openDownloadPluginModal: () => downloadModalManager.openDownloadPluginModal(),
                    handleStopAllPlugins: () => this.#dependencies.handleStopAllPlugins(),
                    openConcurrentPluginsModal: () => concurrentManager.openConcurrentPluginsModal(),
                    handleDownloadChooseFileClick: () => downloadModalManager.handleChooseFileClick(),
                    handleDownloadConfirm: () => downloadModalManager.handleConfirmPluginDownload(),
                    handleDownloadUrlTabClick: () => downloadModalManager.handleUrlTabClick(),
                    handleDownloadFileTabClick: () => downloadModalManager.handleFileTabClick(),
                    handleDownloadManualTabClick: () => downloadModalManager.handleManualPluginTabClick(),
                    handleDownloadManualCopyPath: () => downloadModalManager.handleManualPluginPathCopy(),
                    handleDownloadManualOpenFileExplorer: () => downloadModalManager.handleManualPluginOpenFileExplorer(),
                    handleDownloadManualRestart: () => downloadModalManager.handleManualPluginPowerClick(),
                    handleConfigSave: () => this.#dependencies.getConfigManager().handleSavePluginConfig(),
                    handleInfoCopy: () => this.handleInfoCopyAction()
                },
                backend: {
                    handleBackendInstallStart: () => manageBackendModalManager.handleStartBackendInstall(),
                    handleBackendUpdateCheck: () => manageBackendModalManager.handleCheckBackendUpdate(),
                    handleBackendUninstall: () => manageBackendModalManager.handleUninstallBackend(),
                    handleConcurrentSave: () => concurrentManager.handleSaveConcurrentPlugins(),
                    handleCloneStart: () => this.#dependencies.getCloneManager().handleStartClone(),
                    handleToggleViewMode: () => this.#dependencies.handleToggleViewMode(),
                    handleSortList: () => this.#dependencies.handleSortList(actionElement)
                },
                form: {
                    handleDownloadUrlInput: (inputEvent: Event) => downloadModalManager.handlePluginUrlInput(inputEvent),
                    handleConcurrentSliderInput: (inputEvent: Event) => concurrentManager.handleConcurrentPluginsSliderInput(inputEvent),
                    handleConcurrentValueInput: (inputEvent: Event) => concurrentManager.handleConcurrentPluginsInputChange(inputEvent),
                    handleDownloadFileChange: (changeEvent: Event) => downloadModalManager.handlePluginFileChange(changeEvent)
                }
            },
            event,
            action
        );
    }

    handleMetricBadgeClick(event: Event, target: Element, badgeElement: Element): void {
        const cardController = this.#dependencies.getCardController();
        if (!cardController) {
            throw new Error('PluginsPage card controller is required for metric badge clicks');
        }
        const dispatch = createCardActionDispatcher({
            cardSelector: PLUGIN_ACTION_ITEM_SELECTOR,
            context: 'Plugin metric badge action',
            resolveItem: (card) => {
                const pluginCandidate = cardController.getItemFromCard(card);
                if (!isPluginRecord(pluginCandidate)) {
                    return null;
                }
                return pluginCandidate;
            },
            onAction: ({ item }): void => {
                event.preventDefault();
                event.stopPropagation();
                const badgeType = resolvePluginsMetricBadgeType(target, (selector: string, context?: Element): Element | null => this.#dependencies.pageDom.optional(selector, context));
                if (!badgeType) {
                    throw new Error('Plugin metric badge action requires a metric key');
                }
                const handler = METRIC_BADGE_HANDLERS[badgeType];
                if (handler && handler(this.#dependencies.pluginActionHost, item, target, badgeElement)) return;
                navigateFromPluginsMetricBadge(badgeType, item, this.#dependencies.getRouter());
            }
        });
        if (!(badgeElement instanceof HTMLElement)) {
            throw new Error('Plugin metric badge action requires an HTMLElement action element');
        }
        dispatch({ event, action: PLUGINS_ACTION_METRIC_BADGE, actionElement: badgeElement });
    }

    handleInfoCopyAction(): void {
        this.#dependencies.copyPluginInfo().catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.error('PluginsPage', i18n.t('plugins.notifications.pluginInfoCopyFailed'), runtimeError);
            this.#dependencies.feedback.show(i18n.t('plugins.notifications.pluginInfoCopyFailed'), 'error');
        });
    }
}

export { PluginsInteractionController };
export type { PluginsInteractionControllerDependencies };
