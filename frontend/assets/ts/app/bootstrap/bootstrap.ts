/* SoAI - Frontend application bootstrap coordinator [frontend/assets/ts/app/bootstrap/bootstrap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureBootstrapCore, ensureBootstrapServiceRegistered } from '@app/bootstrap/stages/bootstrapCore.ts';
import { getBootstrapPhase, setBootstrapPhase } from '@app/bootstrap/stages/phases.ts';
import { detectNavigationReload, finalizePreloader } from '@app/bootstrap/stages/preloader.ts';
import { applyTheme, attachStorageThemeListeners } from '@app/bootstrap/stages/theme.ts';
import type { BootstrapApi, BootstrapPhase, Theme } from '@app/bootstrap/stages/types.ts';

const bootstrap: BootstrapApi = Object.freeze({
    applyTheme: (): Theme => {
        ensureBootstrapCore();
        return applyTheme();
    },
    start: (): BootstrapApi => {
        ensureBootstrapCore();
        ensureBootstrapServiceRegistered(bootstrap);
        applyTheme();
        attachStorageThemeListeners();
        setBootstrapPhase('feature');
        return bootstrap;
    },
    getPhase: (): BootstrapPhase => getBootstrapPhase()
});

export { bootstrap, detectNavigationReload, finalizePreloader };
export type { BootstrapApi, BootstrapPhase, Theme, ThemePreference } from '@app/bootstrap/stages/types.ts';
