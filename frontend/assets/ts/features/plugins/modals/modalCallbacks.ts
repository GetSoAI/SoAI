/* SoAI - Plugin modal callback coordination [frontend/assets/ts/features/plugins/modals/modalCallbacks.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ManageBackendManagerHost } from '@features/plugins/modals/backend/managebackendmodal/types.ts';
import type { ConcurrentManagerHost } from '@features/plugins/modals/concurrentmanager/types.ts';
import type { ConfigManagerHost } from '@features/plugins/modals/config/types.ts';
import type { DownloadManagerHost } from '@features/plugins/modals/downloadmanager/service.ts';
import type { InfoManagerHost } from '@features/plugins/modals/InfoManager.ts';

interface PluginsManagerHostCallbacks {
    modals: ModalPresenterApi;
    requireHTMLElement: DownloadManagerHost['view']['requireHTMLElement'];
    optionalHTMLElement: DownloadManagerHost['view']['optionalHTMLElement'];
    queryUI: ConfigManagerHost['queryUI'];
    on: ConfigManagerHost['on'];
    updateText: DownloadManagerHost['view']['updateText'];
    updateHTML: ManageBackendManagerHost['view']['updateHTML'];
    addClassName: DownloadManagerHost['view']['addClassName'];
    removeClassName: DownloadManagerHost['view']['removeClassName'];
    setUIValue: DownloadManagerHost['view']['setUIValue'];
    updateProperty: DownloadManagerHost['view']['updateProperty'];
    updateAttribute: ConcurrentManagerHost['view']['updateAttribute'];
    toggleClassName: DownloadManagerHost['view']['toggleClassName'];
    setDataAttribute: ManageBackendManagerHost['view']['setDataAttribute'];
    setTimeout: ConfigManagerHost['setTimeout'];
    clearTimer: ConfigManagerHost['clearTimer'];
    createConfigurationManager: ConfigManagerHost['createConfigurationManager'];
    copyToClipboard: DownloadManagerHost['session']['copyToClipboard'];
    sanitizeText: InfoManagerHost['sanitizeText'];
    sanitizeClassName: InfoManagerHost['sanitizeClassName'];
    showNotification: (message: string, type?: NotificationType | undefined, duration?: number | undefined) => void;
}

interface PluginsManagerTimingPort {
    setTimeout: PluginsManagerHostCallbacks['setTimeout'];
    clearTimer: PluginsManagerHostCallbacks['clearTimer'];
}

interface PluginsManagerHostCallbacksDependencies {
    modals: PluginsManagerHostCallbacks['modals'];
    requireHTMLElement: PluginsManagerHostCallbacks['requireHTMLElement'];
    optionalHTMLElement: PluginsManagerHostCallbacks['optionalHTMLElement'];
    queryUI: PluginsManagerHostCallbacks['queryUI'];
    on: PluginsManagerHostCallbacks['on'];
    updateText: PluginsManagerHostCallbacks['updateText'];
    updateHTML: PluginsManagerHostCallbacks['updateHTML'];
    addClassName: PluginsManagerHostCallbacks['addClassName'];
    removeClassName: PluginsManagerHostCallbacks['removeClassName'];
    setUIValue: PluginsManagerHostCallbacks['setUIValue'];
    updateProperty: PluginsManagerHostCallbacks['updateProperty'];
    updateAttribute: PluginsManagerHostCallbacks['updateAttribute'];
    toggleClassName: PluginsManagerHostCallbacks['toggleClassName'];
    setDataAttribute: PluginsManagerHostCallbacks['setDataAttribute'];
    timing: PluginsManagerTimingPort;
    createConfigurationManager: PluginsManagerHostCallbacks['createConfigurationManager'];
    copyToClipboard: PluginsManagerHostCallbacks['copyToClipboard'];
    sanitizeText: PluginsManagerHostCallbacks['sanitizeText'];
    sanitizeClassName: PluginsManagerHostCallbacks['sanitizeClassName'];
    showNotification: PluginsManagerHostCallbacks['showNotification'];
}

const createPluginsManagerHostCallbacks = (dependencies: PluginsManagerHostCallbacksDependencies): PluginsManagerHostCallbacks => {
    return {
        modals: dependencies.modals,
        requireHTMLElement: dependencies.requireHTMLElement,
        optionalHTMLElement: dependencies.optionalHTMLElement,
        queryUI: dependencies.queryUI,
        on: dependencies.on,
        updateText: dependencies.updateText,
        updateHTML: dependencies.updateHTML,
        addClassName: dependencies.addClassName,
        removeClassName: dependencies.removeClassName,
        setUIValue: dependencies.setUIValue,
        updateProperty: dependencies.updateProperty,
        updateAttribute: dependencies.updateAttribute,
        toggleClassName: (target: Element | string, className: string, force?: boolean | null): void => dependencies.toggleClassName(target, className, force === null ? undefined : force),
        setDataAttribute: dependencies.setDataAttribute,
        setTimeout: dependencies.timing.setTimeout,
        clearTimer: dependencies.timing.clearTimer,
        createConfigurationManager: dependencies.createConfigurationManager,
        copyToClipboard: dependencies.copyToClipboard,
        sanitizeText: dependencies.sanitizeText,
        sanitizeClassName: dependencies.sanitizeClassName,
        showNotification: dependencies.showNotification
    };
};

export { createPluginsManagerHostCallbacks };
export type { PluginsManagerHostCallbacks, PluginsManagerHostCallbacksDependencies };
