/* SoAI - Shared layout session listeners [frontend/assets/ts/core/layout/sidebar/sessionListeners.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { FIRST_RUN_MODAL_STATE_CHANGED_EVENT } from '@core/firstrun/state.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { SIDEBAR_CUSTOMIZATION_CHANGED_EVENT, SIDEBAR_LANGUAGE_CHANGED_EVENT } from '@core/layout/sidebar/actions.ts';
import type { AuthManagerContract, UserInfo } from '@core/layout/sidebar/contracts.ts';
import type { SidebarDisposerCandidate } from '@core/layout/sidebar/disposers.ts';

interface SidebarSessionListenerDependencies {
    on: (target: EventTarget | Element, event: string, handler: EventListener) => () => void;
    addSessionDisposer: (functionValue: SidebarDisposerCandidate) => () => void;
    refreshSidebar: (options?: { syncRoute?: boolean }) => Promise<void>;
    refreshPluginIndicatorFromStorage: () => Promise<void>;
    setCurrentUser: (user: UserInfo | null) => void;
    refreshGrantedActions: (user: UserInfo | null) => Promise<void>;
    getAuthManager: () => AuthManagerContract | null;
}

const setupSidebarLanguageListener = (dependencies: SidebarSessionListenerDependencies): void => {
    dependencies.addSessionDisposer(
        dependencies.on(window, SIDEBAR_LANGUAGE_CHANGED_EVENT, async () => {
            try {
                await dependencies.refreshSidebar({ syncRoute: true });
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('Sidebar', 'Failed to refresh after language change', runtimeError);
            }
        })
    );
};

const setupSidebarCustomizationListener = (dependencies: SidebarSessionListenerDependencies): void => {
    dependencies.addSessionDisposer(
        dependencies.on(window, SIDEBAR_CUSTOMIZATION_CHANGED_EVENT, async () => {
            try {
                await dependencies.refreshSidebar({ syncRoute: true });
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('Sidebar', 'Failed to refresh after customization change', runtimeError);
            }
        })
    );
};

const setupSidebarFirstRunListener = (dependencies: SidebarSessionListenerDependencies): void => {
    dependencies.addSessionDisposer(
        dependencies.on(window, FIRST_RUN_MODAL_STATE_CHANGED_EVENT, async () => {
            try {
                await dependencies.refreshPluginIndicatorFromStorage();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('Sidebar', 'Failed to refresh first-run indicators', runtimeError);
            }
        })
    );
};

const setupSidebarAuthListener = (dependencies: SidebarSessionListenerDependencies): void => {
    const auth = dependencies.getAuthManager();
    if (!auth?.onLogin || !auth?.onLogout) {
        return;
    }

    const refresh = async (): Promise<void> => {
        const currentUser = auth.user || null;
        dependencies.setCurrentUser(currentUser);
        try {
            await dependencies.refreshGrantedActions(currentUser);
            await dependencies.refreshSidebar({ syncRoute: true });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('Sidebar', 'Auth refresh failed', runtimeError);
        }
    };

    const unsubscribeLogin = auth.onLogin(() => {
        terminateHandledPromise(refresh());
    });
    const unsubscribeLogout = auth.onLogout(() => {
        terminateHandledPromise(refresh());
    });
    dependencies.addSessionDisposer(() => unsubscribeLogin?.());
    dependencies.addSessionDisposer(() => unsubscribeLogout?.());
};

export { setupSidebarAuthListener, setupSidebarCustomizationListener, setupSidebarFirstRunListener, setupSidebarLanguageListener };
export type { SidebarSessionListenerDependencies };
