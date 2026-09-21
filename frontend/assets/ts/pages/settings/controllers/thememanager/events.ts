/* SoAI - Settings page theme manager events [frontend/assets/ts/pages/settings/controllers/thememanager/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { getComputedStyleStrict, getDocumentElement, getEventHub } from '@core/environment/public.ts';
import { normalizeAccentColorPreference } from '@core/theme/accentColor.ts';
import { normalizeSurfaceColorPreference } from '@core/theme/surfaceColor.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import { ThemeColorPreferenceController } from '@pages/settings/controllers/thememanager/ThemeColorPreferenceController.ts';
import { SURFACE_COLOR_PICKER_FALLBACK } from '@pages/settings/controllers/thememanager/themeColorControlsWidget.ts';
import type { AddThemeManagerCleanup, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import { bindSimpleToggleControls, setupChartsEventListeners } from '@pages/settings/controllers/thememanager/effects.ts';

interface ThemeEventsControllerDependencies {
    host: ThemeManagerHost;
    addCleanup: AddThemeManagerCleanup;
    updatePreferenceToggleLabel: (element: Element, enabled?: boolean) => void;
}

class ThemeEventsController {
    readonly #host: ThemeManagerHost;
    readonly #addCleanup: AddThemeManagerCleanup;
    readonly #updatePreferenceToggleLabel: (element: Element, enabled?: boolean) => void;

    constructor({ host, addCleanup, updatePreferenceToggleLabel }: ThemeEventsControllerDependencies) {
        this.#host = host;
        this.#addCleanup = addCleanup;
        this.#updatePreferenceToggleLabel = updatePreferenceToggleLabel;
    }

    setupEventListeners(): void {
        this.#setupThemeEventListeners();
        this.#setupEffectsEventListeners();
        bindSimpleToggleControls({
            host: this.#host,
            addCleanup: this.#addCleanup,
            updatePreferenceToggleLabel: this.#updatePreferenceToggleLabel
        });
        setupChartsEventListeners({
            host: this.#host,
            addCleanup: this.#addCleanup
        });
    }

    #bindPreferenceValueChange(element: HTMLInputElement | HTMLSelectElement, key: UiPreferenceKey): void {
        this.#addCleanup(
            this.#host.pageResources.on(element, 'change', () => {
                this.#host.setUiPrefValue(key, element.value);
            })
        );
    }

    #setupThemeEventListeners(): void {
        const themeSelect = narrowSelect(this.#host.pageDom.requireHTMLElement('theme-select'), 'Theme select');
        const colorController = new ThemeColorPreferenceController(this.#host);
        const accentControl = colorController.requireControl(UI_IDS.ACCENT_COLOR_PICKER, UI_IDS.ACCENT_COLOR_CLEAR, {
            picker: 'Accent color picker',
            clearButton: 'Accent color clear button'
        });
        const surfaceControl = colorController.requireControl(UI_IDS.SURFACE_COLOR_PICKER, UI_IDS.SURFACE_COLOR_CLEAR, {
            picker: 'Surface color picker',
            clearButton: 'Surface color clear button'
        });

        const readThemeDefaultAccent = (): string => {
            const root = getDocumentElement();
            const raw = getComputedStyleStrict(root).getPropertyValue('--accent-green-default').trim();
            const normalized = normalizeAccentColorPreference(raw);
            if (!normalized) {
                throw new Error('Theme default accent color must be a valid hex color');
            }
            return normalized;
        };
        const readSurfaceDefault = (): string => {
            const normalized = normalizeSurfaceColorPreference(SURFACE_COLOR_PICKER_FALLBACK);
            if (!normalized) {
                throw new Error('Theme default surface color must be a valid hex color');
            }
            return normalized;
        };

        const storedAccent = this.#host.getUiPrefValue('accentColor');
        const normalizedAccent = normalizeAccentColorPreference(storedAccent);
        const initialDefaultAccent = readThemeDefaultAccent();
        const activeAccent = normalizedAccent === initialDefaultAccent ? null : normalizedAccent;
        let accentUsesThemeDefault = activeAccent === null;
        colorController.setNullableColor(accentControl, activeAccent, initialDefaultAccent);
        const storedSurface = this.#host.getUiPrefValue('surfaceColor');
        const normalizedSurface = normalizeSurfaceColorPreference(storedSurface);
        const defaultSurface = readSurfaceDefault();
        colorController.setNullableColor(surfaceControl, normalizedSurface, defaultSurface);

        const syncAccentPickerToThemeDefault = (): void => {
            if (accentUsesThemeDefault) {
                accentControl.picker.value = readThemeDefaultAccent();
            }
        };

        this.#addCleanup(
            this.#host.pageResources.on(themeSelect, 'change', () => {
                this.#host.setUiPrefValue('theme', themeSelect.value);
                syncAccentPickerToThemeDefault();
            })
        );
        this.#addCleanup(this.#host.pageResources.on(getEventHub(), 'themeChanged', syncAccentPickerToThemeDefault));

        this.#addCleanup(
            this.#host.pageResources.on(accentControl.picker, 'input', () => {
                const normalized = colorController.readRequiredColor(accentControl, normalizeAccentColorPreference, 'Accent color picker value must be a valid hex color');
                const nextValue = normalized === readThemeDefaultAccent() ? null : normalized;
                accentUsesThemeDefault = nextValue === null;
                this.#host.setUiPrefValue('accentColor', nextValue);
                colorController.setNullableColor(accentControl, nextValue, readThemeDefaultAccent());
            })
        );

        this.#addCleanup(
            this.#host.pageResources.on(accentControl.clearButton, 'click', () => {
                accentUsesThemeDefault = true;
                this.#host.setUiPrefValue('accentColor', null);
                colorController.clearNullableColor(accentControl, readThemeDefaultAccent());
            })
        );

        this.#addCleanup(
            this.#host.pageResources.on(surfaceControl.picker, 'input', () => {
                const normalized = colorController.readRequiredColor(surfaceControl, normalizeSurfaceColorPreference, 'Surface color picker value must be a valid hex color');
                this.#host.setUiPrefValue('surfaceColor', normalized);
                colorController.setNullableColor(surfaceControl, normalized, defaultSurface);
            })
        );

        this.#addCleanup(
            this.#host.pageResources.on(surfaceControl.clearButton, 'click', () => {
                this.#host.setUiPrefValue('surfaceColor', null);
                colorController.clearNullableColor(surfaceControl, defaultSurface);
            })
        );
    }

    #setupEffectsEventListeners(): void {
        const disableAnimationsToggle = narrowInput(this.#host.pageDom.requireHTMLElement('disable-animations-toggle'), 'Disable animations toggle');
        const glassEffectsToggle = narrowInput(this.#host.pageDom.requireHTMLElement('glass-effects-toggle'), 'Glass effects toggle');
        const animationOptionsPanel = this.#host.pageDom.requireHTMLElement('animation-options-panel');

        this.#addCleanup(
            this.#host.pageResources.on(disableAnimationsToggle, 'change', () => {
                const disabled = disableAnimationsToggle.checked;
                this.#host.setUiPrefValue('reduceMotions', disabled);
                this.#updatePreferenceToggleLabel(disableAnimationsToggle, disabled);
                animationOptionsPanel.classList.toggle('u-hidden', disabled);
            })
        );

        this.#addCleanup(
            this.#host.pageResources.on(glassEffectsToggle, 'change', () => {
                const enabled = glassEffectsToggle.checked;
                this.#host.setUiPrefValue('glassEnabled', enabled);
                this.#updatePreferenceToggleLabel(glassEffectsToggle, enabled);
            })
        );

        const animationSelectBindings: Array<[string, UiPreferenceKey]> = [
            ['page-animation-select', 'pageAnimation'],
            ['modal-animation-select', 'modalAnimation'],
            ['notification-animation-select', 'notificationAnimation'],
            ['animation-speed-select', 'animationSpeed'],
            ['default-page-select', 'defaultPage']
        ];
        for (const [elementId, prefKey] of animationSelectBindings) {
            const select = narrowSelect(this.#host.pageDom.requireHTMLElement(elementId), `${prefKey} select`);
            this.#bindPreferenceValueChange(select, prefKey);
        }
    }
}

export { ThemeEventsController };
