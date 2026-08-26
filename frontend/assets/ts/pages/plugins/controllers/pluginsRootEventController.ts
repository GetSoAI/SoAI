/* SoAI - Plugins page root event controller [frontend/assets/ts/pages/plugins/controllers/pluginsRootEventController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { PLUGINS_ACTION_METRIC_BADGE } from '@features/plugins/public.ts';
import { isPluginsCardActionId, type PluginsActionId, type PluginsCardActionId } from '@pages/plugins/actions.ts';

interface PluginsRootEventControllerHost {
    handleCardActionClick(event: Event, actionElement: Element, action: PluginsCardActionId): void;
    handlePageActionEvent(event: Event, action: PluginsActionId, actionElement: Element): boolean;
    handleMetricBadgeClick(event: Event, target: Element, badgeElement: Element): void;
    handleActionError(error: Error, message: string): void;
}

interface PluginsRootEventControllerConfig {
    host: PluginsRootEventControllerHost;
    shouldPreventDefaultForActionElement: (element: Element) => boolean;
}

interface PluginsRootEventController {
    handleRootClick(event: Event, action: PluginsActionId, resolvedActionElement: HTMLElement | null): void;
    handleRootChange(event: Event, action: PluginsActionId, resolvedActionElement: HTMLElement | null): void;
}

const createPluginsRootEventController = (config: PluginsRootEventControllerConfig): PluginsRootEventController => {
    const { host, shouldPreventDefaultForActionElement } = config;

    const handleRootActionEvent = (event: Event, action: PluginsActionId, actionElement: Element): void => {
        if (action === PLUGINS_ACTION_METRIC_BADGE) {
            host.handleMetricBadgeClick(event, actionElement, actionElement);
            return;
        }
        if (isPluginsCardActionId(action)) {
            host.handleCardActionClick(event, actionElement, action);
            return;
        }
        if (host.handlePageActionEvent(event, action, actionElement)) {
            if (event.type === 'click' && shouldPreventDefaultForActionElement(actionElement)) {
                event.preventDefault();
                event.stopPropagation();
            }
        }
    };

    const handleRootClick = (event: Event, action: PluginsActionId, resolvedActionElement: HTMLElement | null): void => {
        try {
            if (event.defaultPrevented) {
                return;
            }
            const actionElement = resolvedActionElement;
            if (!actionElement) {
                return;
            }
            handleRootActionEvent(event, action, actionElement);
        } catch (error) {
            const runtimeError = ensureError(error);
            host.handleActionError(runtimeError, i18n.t('plugins.errors.clickHandlerFailed'));
        }
    };

    const handleRootChange = (event: Event, action: PluginsActionId, resolvedActionElement: HTMLElement | null): void => {
        try {
            if (!resolvedActionElement) {
                return;
            }
            handleRootActionEvent(event, action, resolvedActionElement);
        } catch (error) {
            const runtimeError = ensureError(error);
            host.handleActionError(runtimeError, i18n.t('plugins.errors.changeHandlerFailed'));
        }
    };

    return {
        handleRootClick,
        handleRootChange
    };
};

export { createPluginsRootEventController };
export type { PluginsRootEventController, PluginsRootEventControllerConfig, PluginsRootEventControllerHost };
