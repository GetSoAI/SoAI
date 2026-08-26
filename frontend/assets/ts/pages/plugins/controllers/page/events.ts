/* SoAI - Plugins page events [frontend/assets/ts/pages/plugins/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { disposeManagedModalLifecycles } from '@core/modals/managedModalLifecycle.ts';
import type { PluginsPageSession } from '@pages/plugins/controllers/page/PluginsPageSession.ts';

interface PluginsPageDestroyRuntime {
    modalManagers: {
        downloadModalManager: { disposeForPageDestroy(): void };
        configManager: { disposeForPageDestroy(): void };
        infoManager: { disposeForPageDestroy(): void };
        concurrentManager: { disposeForPageDestroy(): void };
        manageBackendModalManager: { disposeForPageDestroy(): void };
        cloneManager: { disposeForPageDestroy(): void };
    };
    progressController: { dispose(): void };
    catalogSubscriptions: { cleanup(): void };
}

interface CleanupPluginsPageOnDestroyDependencies {
    session: PluginsPageSession;
    runtime: PluginsPageDestroyRuntime;
}

interface PluginsDestroyDependencies {
    disposeModalManagers(): void;
    disposeProgressController(): void;
    cleanupCatalogSubscriptions(): void;
    disposeCardController(): void;
    clearSession(): void;
}

const destroyPluginsPageResources = (dependencies: PluginsDestroyDependencies): void => {
    const failures: Error[] = [];
    runCleanupStepCollectingFailure(() => dependencies.disposeModalManagers(), failures);
    runCleanupStepCollectingFailure(() => dependencies.disposeProgressController(), failures);
    runCleanupStepCollectingFailure(() => dependencies.cleanupCatalogSubscriptions(), failures);
    runCleanupStepCollectingFailure(() => dependencies.disposeCardController(), failures);
    runCleanupStepCollectingFailure(() => dependencies.clearSession(), failures);
    throwCollectedCleanupFailures(failures);
};

const cleanupPluginsPageOnDestroy = (dependencies: CleanupPluginsPageOnDestroyDependencies): void => {
    destroyPluginsPageResources({
        disposeModalManagers: (): void => {
            disposeManagedModalLifecycles([dependencies.runtime.modalManagers.downloadModalManager, dependencies.runtime.modalManagers.configManager, dependencies.runtime.modalManagers.infoManager, dependencies.runtime.modalManagers.concurrentManager, dependencies.runtime.modalManagers.manageBackendModalManager, dependencies.runtime.modalManagers.cloneManager]);
        },
        disposeProgressController: (): void => dependencies.runtime.progressController.dispose(),
        cleanupCatalogSubscriptions: (): void => dependencies.runtime.catalogSubscriptions.cleanup(),
        disposeCardController: (): void => {
            if (!dependencies.session.cardController) {
                throw new Error('PluginsPage destroy requires cardController');
            }
            dependencies.session.cardController.dispose();
        },
        clearSession: (): void => dependencies.session.clearTransientState()
    });
};

export { cleanupPluginsPageOnDestroy };
export type { CleanupPluginsPageOnDestroyDependencies, PluginsPageDestroyRuntime };
