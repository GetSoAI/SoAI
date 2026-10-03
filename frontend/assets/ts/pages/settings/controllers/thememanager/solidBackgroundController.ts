/* SoAI - Settings solid background preference controller [frontend/assets/ts/pages/settings/controllers/thememanager/solidBackgroundController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { UI_IDS } from '@features/settings/public.ts';
import { commitSolidBackground } from '@pages/settings/controllers/thememanager/backgroundSelection.ts';
import { updateWallpaperUI } from '@pages/settings/controllers/thememanager/effects.ts';
import { ThemeColorPreferenceController, type ThemeColorControl } from '@pages/settings/controllers/thememanager/ThemeColorPreferenceController.ts';
import { SOLID_BACKGROUND_PICKER_FALLBACK } from '@pages/settings/controllers/thememanager/themeColorControlsWidget.ts';
import type { AddThemeManagerCleanup, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import { requireUiPrefsSolidBackground } from '@pages/settings/controllers/uiprefs/guards.ts';

interface ThemeSolidBackgroundControllerDependencies {
    host: ThemeManagerHost;
    addCleanup: AddThemeManagerCleanup;
}

const requireSolidBackgroundControl = (host: ThemeManagerHost): { colorController: ThemeColorPreferenceController; solidControl: ThemeColorControl } => {
    const colorController = new ThemeColorPreferenceController(host);
    const solidControl = colorController.requireControl(UI_IDS.SOLID_BACKGROUND_PICKER, UI_IDS.SOLID_BACKGROUND_CLEAR, {
        picker: 'Solid background picker',
        clearButton: 'Solid background clear button'
    });
    return { colorController, solidControl };
};

const syncSolidBackgroundControl = (host: ThemeManagerHost): void => {
    const { colorController, solidControl } = requireSolidBackgroundControl(host);
    colorController.setNullableColor(solidControl, host.storage.getSolidBackground(), SOLID_BACKGROUND_PICKER_FALLBACK);
};

class ThemeSolidBackgroundController {
    readonly #host: ThemeManagerHost;
    readonly #addCleanup: AddThemeManagerCleanup;

    constructor({ host, addCleanup }: ThemeSolidBackgroundControllerDependencies) {
        this.#host = host;
        this.#addCleanup = addCleanup;
    }

    setupEventListeners(): void {
        const { colorController, solidControl } = requireSolidBackgroundControl(this.#host);
        syncSolidBackgroundControl(this.#host);

        this.#addCleanup(
            this.#host.pageResources.on(solidControl.picker, 'input', () => {
                colorController.setNullableColor(solidControl, requireUiPrefsSolidBackground(solidControl.picker.value), SOLID_BACKGROUND_PICKER_FALLBACK);
            })
        );
        this.#addCleanup(
            this.#host.pageResources.on(solidControl.picker, 'change', () => {
                this.#commit(requireUiPrefsSolidBackground(solidControl.picker.value));
            })
        );
        this.#addCleanup(
            this.#host.pageResources.on(solidControl.clearButton, 'click', () => {
                this.#commit(null);
            })
        );
    }

    #commit(color: string | null): void {
        commitSolidBackground(this.#host, color);
        syncSolidBackgroundControl(this.#host);
        if (this.#host.canManageWallpaper()) {
            updateWallpaperUI(this.#host);
        }
    }
}

export { syncSolidBackgroundControl, ThemeSolidBackgroundController };
