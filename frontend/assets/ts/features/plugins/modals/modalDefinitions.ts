/* SoAI - Plugin modal definitions [frontend/assets/ts/features/plugins/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import { downloadPluginModalDefinition } from '@features/plugins/modals/downloadPluginModal.ts';
import { pluginConfigModalDefinition } from '@features/plugins/modals/pluginConfigModal.ts';
import { pluginInfoModalDefinition } from '@features/plugins/modals/pluginInfoModal.ts';
import { manageBackendModalDefinition } from '@features/plugins/modals/backendModals.ts';
import { concurrentPluginsModalDefinition } from '@features/plugins/modals/concurrentPluginsModal.ts';
import { clonePluginModalDefinition } from '@features/plugins/modals/clonePluginModal.ts';
import { createPluginsIntroModalDefinition } from '@features/plugins/modals/pluginsIntroModal.ts';

const createPluginsModalDefinitions = (dependencies: { storage: FirstRunStateStorage }): readonly ModalDefinition[] => {
    return Object.freeze([downloadPluginModalDefinition, pluginConfigModalDefinition, pluginInfoModalDefinition, manageBackendModalDefinition, concurrentPluginsModalDefinition, clonePluginModalDefinition, createPluginsIntroModalDefinition(dependencies.storage)]);
};

export { createPluginsModalDefinitions };
