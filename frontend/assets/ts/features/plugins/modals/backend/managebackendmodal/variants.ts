/* SoAI - Manage backend modal variant loading [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/variants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { loadBackendVariantSelector } from '@features/plugins/modals/backend/backendVariantSelector.ts';
import type { BackendManagerDependencies, ManageState } from '@features/plugins/modals/backend/managebackendmodal/types.ts';
import { renderManageBackendVariantInfo, setManageBackendButtonsDisabled } from '@features/plugins/modals/backend/managebackendmodal/view.ts';

interface ManageBackendVariantLoadDependencies extends BackendManagerDependencies {
    state: ManageState;
    variantLoadToken: SequenceToken;
}

const loadManageBackendVariants = async (dependencies: ManageBackendVariantLoadDependencies, modalId: string, modalRoot: HTMLElement, plugin: PluginRecord, token: number): Promise<void> => {
    const payload = await loadBackendVariantSelector({ host: dependencies.host, security: dependencies.security }, modalId, modalRoot, String(plugin.name), {
        disabled: false,
        isCurrent: (): boolean => dependencies.variantLoadToken.isActive(token) && dependencies.state.currentPlugin?.name === plugin.name
    });
    if (!dependencies.variantLoadToken.isActive(token) || dependencies.state.currentPlugin?.name !== plugin.name) {
        return;
    }
    const loaded = payload !== null;
    if (payload) {
        renderManageBackendVariantInfo(dependencies.host.view, modalId, modalRoot, payload);
    }
    dependencies.state.backendVariantsReady = loaded;
    setManageBackendButtonsDisabled({ host: dependencies.host, classNames: dependencies.classNames }, modalId, modalRoot, !loaded);
};

export { loadManageBackendVariants };
