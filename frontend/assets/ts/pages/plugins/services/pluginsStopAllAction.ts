/* SoAI - Plugins page stop all action [frontend/assets/ts/pages/plugins/services/pluginsStopAllAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stopAllPluginsActionPath } from '@core/api/endpoints/uiPaths.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiRequestBody } from '@core/api/types/request.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface PluginsStopAllHost extends PageFeedbackOwnerHost {
    getCollectionPlugins(): PluginRecord[];
    isPluginStoppable(plugin: PluginRecord): boolean;
    updateStopAllButtonVisibility(): void;
    runPageTask<T>(taskKey: string, task: () => Promise<T>, options: { displayName: string; rethrow: boolean }): Promise<T | null>;
    post(path: string, body?: ApiRequestBody): Promise<ApiResponsePayload>;
}

const handleStopAllPluginsAction = async (host: PluginsStopAllHost): Promise<void> => {
    const stoppable = host.getCollectionPlugins().filter((plugin) => host.isPluginStoppable(plugin));
    if (!stoppable.length) {
        host.updateStopAllButtonVisibility();
        host.feedback.show(i18n.t('plugins.notifications.noPluginsToStop'), 'warning');
        return;
    }

    const confirmed = await requireDialogsService().showConfirmation({
        title: i18n.t('plugins.confirmations.stopAll'),
        message: i18n.plural('plugins.confirmations.stopAllMessage', stoppable.length, { count: stoppable.length }),
        confirmText: i18n.t('plugins.confirmations.stopAllButton'),
        cancelText: i18n.t('plugins.confirmations.stopAllCancel')
    });
    if (!confirmed) {
        return;
    }

    const result = await host.runPageTask('plugins.stopAllPlugins', () => host.post(stopAllPluginsActionPath(), null), { displayName: i18n.t('plugins.confirmations.stopAll'), rethrow: false });
    const resultObject = isJsonObject(result) ? result : null;
    if (!resultObject) {
        return;
    }
    const message = toTrimmedString(resultObject['message']);
    if (message) {
        host.feedback.show(message, 'success');
    } else {
        host.feedback.show(i18n.t('plugins.notifications.stopAllSuccess'), 'success');
    }
};

export { handleStopAllPluginsAction };
export type { PluginsStopAllHost };
