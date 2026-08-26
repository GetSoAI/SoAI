/* SoAI - Settings solid background preference controller [frontend/assets/ts/pages/settings/controllers/thememanager/solidBackgroundController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { UI_IDS } from '@features/settings/public.ts';
import { ThemeColorPreferenceController } from '@pages/settings/controllers/thememanager/ThemeColorPreferenceController.ts';
import { SOLID_BACKGROUND_PICKER_FALLBACK } from '@pages/settings/controllers/thememanager/themeColorControlsWidget.ts';
import type { AddThemeManagerCleanup, RunDetachedWithBoundary, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import { requireUiPrefsSolidBackground } from '@pages/settings/controllers/uiprefs/guards.ts';

interface ThemeSolidBackgroundControllerDependencies {
    host: ThemeManagerHost;
    addCleanup: AddThemeManagerCleanup;
    runDetachedWithBoundary: RunDetachedWithBoundary;
}

class ThemeSolidBackgroundController {
    readonly #host: ThemeManagerHost;
    readonly #addCleanup: AddThemeManagerCleanup;
    readonly #runDetachedWithBoundary: RunDetachedWithBoundary;

    constructor({ host, addCleanup, runDetachedWithBoundary }: ThemeSolidBackgroundControllerDependencies) {
        this.#host = host;
        this.#addCleanup = addCleanup;
        this.#runDetachedWithBoundary = runDetachedWithBoundary;
    }

    setupEventListeners(): void {
        const colorController = new ThemeColorPreferenceController(this.#host);
        const solidControl = colorController.requireControl(UI_IDS.SOLID_BACKGROUND_PICKER, UI_IDS.SOLID_BACKGROUND_CLEAR, {
            picker: 'Solid background picker',
            clearButton: 'Solid background clear button'
        });
        const currentColor = requireUiPrefsSolidBackground(this.#host.getUiPrefValue('solidBackground'));
        colorController.setNullableColor(solidControl, currentColor, SOLID_BACKGROUND_PICKER_FALLBACK);

        this.#addCleanup(
            this.#host.pageResources.on(solidControl.picker, 'input', () => {
                const color = requireUiPrefsSolidBackground(solidControl.picker.value);
                this.#host.setUiPrefValue('solidBackground', color);
                colorController.setNullableColor(solidControl, color, SOLID_BACKGROUND_PICKER_FALLBACK);
            })
        );
        this.#addCleanup(
            this.#host.pageResources.on(solidControl.clearButton, 'click', () => {
                this.#runDetachedWithBoundary('settings:theme:clearSolidBackground', async () => {
                    await this.#clearSolidBackground();
                });
            })
        );
    }

    async #clearSolidBackground(): Promise<void> {
        const colorController = new ThemeColorPreferenceController(this.#host);
        const solidControl = colorController.requireControl(UI_IDS.SOLID_BACKGROUND_PICKER, UI_IDS.SOLID_BACKGROUND_CLEAR, {
            picker: 'Solid background picker',
            clearButton: 'Solid background clear button'
        });
        this.#host.setUiPrefValue('solidBackground', null);
        colorController.clearNullableColor(solidControl, SOLID_BACKGROUND_PICKER_FALLBACK);
    }
}

export { ThemeSolidBackgroundController };
