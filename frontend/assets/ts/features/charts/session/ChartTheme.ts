/* SoAI - Chart theme observation and palette ownership [frontend/assets/ts/features/charts/session/ChartTheme.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scheduleRequiredRender } from '@core/runtime/animationFrames.ts';
import { LifecycleResources } from '@core/lifecyclemodel/LifecycleResources.ts';
import type { ChartColorInput, ColorPalette, ThemeStyles } from '@features/charts/chartTypes.ts';
import { CSS_COLOR_VAR_MAP, THEME_DEPENDENT_COLOR_KEYS } from '@features/charts/component/chartComponentStatics.ts';
import { getStyleSources, readCssVariable } from '@features/charts/component/state/adapters.ts';
import { applyAlphaToColor, getThemeStyles, resolveDynamicPrimaryColor } from '@features/charts/component/state/service.ts';
import type { ChartConfigurationState } from '@features/charts/session/chartState.ts';

interface ChartThemeDependencies {
    configuration: ChartConfigurationState;
    surface: { readonly element: HTMLElement };
    settings: { update(options: { colors: ColorPalette }): void };
}

class ChartTheme {
    readonly #configuration: ChartConfigurationState;
    readonly #surface: ChartThemeDependencies['surface'];
    readonly #settings: ChartThemeDependencies['settings'];
    readonly #resources = new LifecycleResources();
    #cancelRefresh: (() => void) | null = null;
    #active = false;
    #frameStyles: { value: ThemeStyles | null } | null = null;

    constructor({ configuration, surface, settings }: ChartThemeDependencies) {
        this.#configuration = configuration;
        this.#surface = surface;
        this.#settings = settings;
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
        if (this.#active) return;
        const win = this.#surface.element.ownerDocument.defaultView;
        if (!win) throw new Error('Chart requires a Window to observe theme changes');
        this.#active = true;
        this.#resources.addEventListener(win, 'themeChanged', () => this.#scheduleRefresh());
    }

    beginFrame(): void {
        if (this.#frameStyles !== null) throw new Error('Chart theme frame is already active');
        this.#frameStyles = { value: null };
    }

    endFrame(): void {
        this.#frameStyles = null;
    }

    getStyles(): ThemeStyles {
        if (this.#frameStyles === null) return getThemeStyles(this.#surface.element, this.#configuration.options.colors);
        this.#frameStyles.value ??= getThemeStyles(this.#surface.element, this.#configuration.options.colors);
        return this.#frameStyles.value;
    }

    applyAlpha(color: ChartColorInput, alpha: number | string | null | undefined, fallback: string | null = null): string {
        return applyAlphaToColor(color, alpha, fallback);
    }

    resolveDynamicPrimaryColor(): string | null {
        return resolveDynamicPrimaryColor({ chartOptions: this.#configuration.options });
    }

    refresh(): void {
        const keys = THEME_DEPENDENT_COLOR_KEYS.filter((key) => this.#configuration.themeColorFlags[key]);
        if (keys.length === 0) return;
        const styles = getStyleSources(this.#surface.element);
        const colors: ColorPalette = {};
        for (const key of keys) {
            const variable = CSS_COLOR_VAR_MAP[key];
            const value = readCssVariable(styles, variable);
            if (value) colors[key] = value;
        }
        if (Object.keys(colors).length === 0) return;
        colors['__themeManaged'] = JSON.stringify(Object.fromEntries(keys.map((key) => [key, true])));
        this.#settings.update({ colors });
    }

    async destroy(): Promise<void> {
        this.#active = false;
        this.#frameStyles = null;
        this.#cancelRefresh?.();
        this.#cancelRefresh = null;
        await this.#resources.cleanup();
    }

    #scheduleRefresh(): void {
        if (!this.#active || this.#cancelRefresh !== null) return;
        this.#cancelRefresh = scheduleRequiredRender(() => {
            this.#cancelRefresh = null;
            if (this.#active) this.refresh();
        });
    }
}

export { ChartTheme };
export type { ChartThemeDependencies };
