/* SoAI - Settings theme manager ownership [frontend/assets/ts/pages/settings/controllers/thememanager/ThemeManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { ToggleLabelState } from '@core/toggleSwitch.ts';
import { getPreferenceStateLabels, SettingsSectionLifecycle } from '@features/settings/public.ts';
import { runDetachedWithBoundary } from '@pages/settings/controllers/page/detachedBoundaries.ts';
import type { ThemeManagerDependencies, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import { ThemeCustomizationController } from '@pages/settings/controllers/thememanager/controller.ts';
import { ThemeEventsController } from '@pages/settings/controllers/thememanager/events.ts';
import { ThemeSolidBackgroundController } from '@pages/settings/controllers/thememanager/solidBackgroundController.ts';
import { ThemeWallpaperController } from '@pages/settings/controllers/thememanager/service.ts';
import { renderThemeSection } from '@pages/settings/controllers/thememanager/view.ts';

class ThemeManager {
    readonly #host: ThemeManagerHost;
    readonly #canManageSolidBackground: boolean;
    readonly #eventsController: ThemeEventsController;
    readonly #customizationController: ThemeCustomizationController;
    readonly #solidBackgroundController: ThemeSolidBackgroundController;
    readonly #wallpaperController: ThemeWallpaperController;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();

    constructor({ host, canManageSolidBackground, dashboardProductTitle, updatePreferenceToggleLabel }: ThemeManagerDependencies) {
        if (!host) {
            throw new Error('ThemeManager requires a host');
        }

        this.#host = host;
        this.#canManageSolidBackground = canManageSolidBackground;
        this.#eventsController = new ThemeEventsController({
            host,
            addCleanup: (cleanup) => {
                this.#lifecycle.addCleanup(cleanup);
            },
            updatePreferenceToggleLabel
        });
        this.#customizationController = new ThemeCustomizationController({
            host,
            dashboardProductTitle,
            addCleanup: (cleanup) => {
                this.#lifecycle.addCleanup(cleanup);
            }
        });
        this.#solidBackgroundController = new ThemeSolidBackgroundController({
            host,
            addCleanup: (cleanup) => {
                this.#lifecycle.addCleanup(cleanup);
            },
            runDetachedWithBoundary: (operationName, task) => {
                runDetachedWithBoundary(host, operationName, task);
            }
        });
        this.#wallpaperController = new ThemeWallpaperController({
            host,
            addCleanup: (cleanup) => {
                this.#lifecycle.addCleanup(cleanup);
            },
            runDetachedWithBoundary: (operationName, task) => {
                runDetachedWithBoundary(host, operationName, task);
            },
            isMounted: () => this.#lifecycle.isMounted
        });
    }

    render(): TrustedHtml {
        const viewContext = {
            host: this.#host,
            canManageSolidBackground: this.#canManageSolidBackground,
            canManageWallpaper: this.#host.canManageWallpaper(),
            getPreferenceStateLabels: () => this.#getPreferenceStateLabels()
        };
        return toTrustedUiHtml(renderThemeSection(viewContext));
    }

    setupEventListeners(): void {
        this.dispose();
        this.#lifecycle.mount();
        this.#eventsController.setupEventListeners();
        if (this.#canManageSolidBackground) {
            this.#solidBackgroundController.setupEventListeners();
        }
        if (this.#host.canManageWallpaper()) {
            this.#wallpaperController.setupEventListeners();
        }
        this.#customizationController.setupCustomizationSection('sidebar');
        this.#customizationController.setupCustomizationSection('dashboard');
    }

    async reload(): Promise<void> {
        if (this.#host.canManageWallpaper()) {
            await this.#wallpaperController.reload();
        }
    }

    dispose(): void {
        try {
            this.#lifecycle.dispose('theme-manager-dispose');
        } finally {
            this.#wallpaperController.dispose();
        }
    }

    #getPreferenceStateLabels(): ToggleLabelState {
        return getPreferenceStateLabels();
    }
}

export { ThemeManager };
