/* SoAI - Frontend application fresh install recovery [frontend/assets/ts/app/bootstrap/stages/applifecycle/freshInstallRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toggleMainUIVisibility } from '@app/bootstrap/stages/applifecycle/dom.ts';
import { ensureRouteRendered } from '@app/bootstrap/stages/applifecycle/routing.ts';
import type { AppLifecycleDependencies } from '@app/bootstrap/stages/applifecycle/types.ts';
import type { WizardStatus } from '@core/auth/public.ts';
import { isFreshInstallWizardStatus } from '@core/auth/wizardStatus.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { AUTH_ROUTE_WIZARD } from '@core/routing/router/authRouteTarget.ts';

type FreshInstallRecovery = () => Promise<boolean>;

interface FreshInstallRecoveryState {
    task: Promise<boolean> | null;
}

const recoveryStates: WeakMap<AppLifecycleDependencies, FreshInstallRecoveryState> = new WeakMap();

const resolveWizardStatus = async (dependencies: AppLifecycleDependencies): Promise<WizardStatus | null> => {
    try {
        await dependencies.auth.checkWizardStatus();
        return dependencies.auth.getWizardStatusSnapshot();
    } catch (error) {
        errorHandler.warn('AppLifecycle', 'Fresh install wizard status probe failed', ensureError(error));
        return null;
    }
};

const clearFreshInstallSession = async (dependencies: AppLifecycleDependencies, status: WizardStatus): Promise<void> => {
    await dependencies.auth.initialize({
        wizardState: status,
        skipSessionProbe: true
    });
    dependencies.storage.clearRedirectAfterLogin();
    dependencies.soaiOsCapabilities.clearAccess();
};

const navigateFreshInstallWizard = async (dependencies: AppLifecycleDependencies): Promise<void> => {
    toggleMainUIVisibility(false, dependencies.state);
    await dependencies.router.navigate(AUTH_ROUTE_WIZARD, { force: true, replace: true });
    await ensureRouteRendered({
        route: AUTH_ROUTE_WIZARD,
        router: dependencies.router
    });
};

const runFreshInstallRecovery = async (dependencies: AppLifecycleDependencies): Promise<boolean> => {
    const status = await resolveWizardStatus(dependencies);
    if (!isFreshInstallWizardStatus(status)) {
        return false;
    }
    await clearFreshInstallSession(dependencies, status);
    await navigateFreshInstallWizard(dependencies);
    return true;
};

const createFreshInstallRecovery = (dependencies: AppLifecycleDependencies, state: FreshInstallRecoveryState): FreshInstallRecovery => {
    return async (): Promise<boolean> => {
        if (state.task) {
            return state.task;
        }
        state.task = runFreshInstallRecovery(dependencies).finally(() => {
            state.task = null;
        });
        return state.task;
    };
};

const getFreshInstallRecovery = (dependencies: AppLifecycleDependencies): FreshInstallRecovery => {
    let state = recoveryStates.get(dependencies);
    if (!state) {
        state = {
            task: null
        };
        recoveryStates.set(dependencies, state);
    }
    return createFreshInstallRecovery(dependencies, state);
};

export { getFreshInstallRecovery };
