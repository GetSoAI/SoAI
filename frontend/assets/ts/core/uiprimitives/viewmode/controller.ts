/* SoAI - Shared UI primitives controller [frontend/assets/ts/core/uiprimitives/viewmode/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyViewModeButton } from '@core/uiprimitives/viewmode/button.ts';
import { createViewModeValidator, persistViewMode } from '@core/uiprimitives/viewmode/storage.ts';
import type { ViewMode, ViewModeControllerOptions, ViewModeOption } from '@core/uiprimitives/viewmode/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

class ViewModeController {
    readonly #root: HTMLElement;
    readonly #button: HTMLButtonElement;
    readonly #modes: readonly [ViewMode, ViewMode];
    readonly #storageKey: string;
    readonly #labels: Record<ViewMode, string>;
    readonly #icons: Record<ViewMode, IconName>;
    readonly #getIconSync: ViewModeControllerOptions['getIconSync'];
    readonly #onModeChanging: ((mode: ViewMode) => void) | null;
    readonly #onModeChanged: ((mode: ViewMode) => void) | null;
    #mode: ViewMode;

    constructor(options: ViewModeControllerOptions) {
        const validate = createViewModeValidator(options.modes);
        if (!validate(options.activeMode)) {
            throw new Error(`Invalid initial view mode "${options.activeMode}"`);
        }
        const rootMode = options.root.dataset['viewMode'];
        if (rootMode !== options.activeMode) {
            options.root.dataset['viewMode'] = options.activeMode;
        }
        this.#root = options.root;
        this.#button = options.button;
        this.#modes = options.modes;
        this.#storageKey = options.storageKey;
        this.#labels = options.labels;
        this.#icons = options.icons;
        this.#getIconSync = options.getIconSync;
        this.#onModeChanging = options.onModeChanging ?? null;
        this.#onModeChanged = options.onModeChanged ?? null;
        this.#mode = options.activeMode;
        this.#apply();
    }

    getMode(): ViewMode {
        return this.#mode;
    }

    setMode(mode: ViewMode): void {
        const validate = createViewModeValidator(this.#modes);
        if (!validate(mode)) {
            throw new Error(`Unsupported view mode "${mode}"`);
        }
        if (mode === this.#mode) {
            this.#apply();
            return;
        }
        this.#onModeChanging?.(mode);
        this.#mode = mode;
        this.#root.dataset['viewMode'] = mode;
        persistViewMode(this.#storageKey, mode);
        this.#apply();
        this.#onModeChanged?.(mode);
    }

    toggle(): void {
        this.setMode(this.#mode === this.#modes[0] ? this.#modes[1] : this.#modes[0]);
    }

    #apply(): void {
        const option: ViewModeOption = {
            mode: this.#mode,
            icon: this.#icons[this.#mode],
            label: this.#labels[this.#mode],
            pressed: this.#mode === this.#modes[1]
        };
        applyViewModeButton(this.#button, option, (viewModeOption) => this.#getIconSync(viewModeOption.icon, { size: 24, strokeWidth: 1.5 }));
    }
}

export { ViewModeController };
