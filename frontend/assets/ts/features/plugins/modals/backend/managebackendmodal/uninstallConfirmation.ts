/* SoAI - Manage backend uninstall confirmation dialog [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/uninstallConfirmation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';

interface ManageBackendUninstallConfirmationHost {
    formatPluginName(name: string): string;
}

const confirmManageBackendUninstall = async (host: ManageBackendUninstallConfirmationHost, plugin: PluginRecord): Promise<boolean> => {
    const pluginLabel = String(plugin.displayName ?? '').trim() || host.formatPluginName(String(plugin.name)) || String(plugin.name);
    return await requireDialogsService().showConfirmation({
        title: i18n.t('plugins.confirmations.uninstallBackend'),
        message: i18n.t('plugins.confirmations.uninstallMessage', { plugin: pluginLabel }),
        confirmText: i18n.t('plugins.confirmations.uninstallButton'),
        cancelText: i18n.t('plugins.confirmations.uninstallCancel')
    });
};

export { confirmManageBackendUninstall };
