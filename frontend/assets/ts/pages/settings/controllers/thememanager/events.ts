/* SoAI - Settings page theme manager events [frontend/assets/ts/pages/settings/controllers/thememanager/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { resolveDefaultAuthenticatedRoute } from '@core/routing/router/authRouteTarget.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
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
    readonly #projections: Array<() => void> = [];
    readonly #addCleanup: AddThemeManagerCleanup;
    readonly #updatePreferenceToggleLabel: (element: Element, enabled?: boolean) => void;

    constructor({ host, addCleanup, updatePreferenceToggleLabel }: ThemeEventsControllerDependencies) {
        this.#host = host;
        this.#addCleanup = addCleanup;
        this.#updatePreferenceToggleLabel = updatePreferenceToggleLabel;
    }

    setupEventListeners(): void {
        this.dispose();
        this.#setupThemeEventListeners();
        this.#setupEffectsEventListeners();
        bindSimpleToggleControls({
            host: this.#host,
            addPreferenceProjection: (project) => this.#projections.push(project),
            addCleanup: this.#addCleanup,
            updatePreferenceToggleLabel: this.#updatePreferenceToggleLabel
        });
        setupChartsEventListeners({
            host: this.#host,
            addPreferenceProjection: (project) => this.#projections.push(project),
            addCleanup: this.#addCleanup
        });
    }

    syncUiPreferences(): void {
        for (const project of this.#projections) project();
    }

    dispose(): void {
        this.#projections.length = 0;
    }

    #bindPreferenceValueChange(element: HTMLInputElement | HTMLSelectElement, key: UiPreferenceKey): void {
        this.#projections.push(() => {
            const value = this.#host.getUiPrefValue(key);
            if (value !== null && typeof value !== 'string') throw new TypeError(`uiPrefs.${key} must be a string or null`);
            const selection = key === 'defaultPage' ? resolveDefaultAuthenticatedRoute(value, getAuthManager()) : (value ?? '');
            if (element instanceof HTMLSelectElement && element.value !== selection) setSelectValueAndSyncDefault(element, selection);
            else if (element.value !== selection) element.value = selection;
        });
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

        const syncColors = (): void => {
            const defaultAccent = readThemeDefaultAccent();
            const accent = normalizeAccentColorPreference(this.#host.getUiPrefValue('accentColor'));
            colorController.setNullableColor(accentControl, accent === defaultAccent ? null : accent, defaultAccent);
            colorController.setNullableColor(surfaceControl, normalizeSurfaceColorPreference(this.#host.getUiPrefValue('surfaceColor')), readSurfaceDefault());
        };
        this.#projections.push(syncColors);
        syncColors();
        this.#bindPreferenceValueChange(themeSelect, 'theme');
        const syncAccentPickerToThemeDefault = (): void => {
            const accent = normalizeAccentColorPreference(this.#host.getUiPrefValue('accentColor'));
            if (accent === null || accent === readThemeDefaultAccent()) colorController.setNullableColor(accentControl, null, readThemeDefaultAccent());
        };

        this.#addCleanup(
            this.#host.pageResources.on(themeSelect, 'change', () => {
                syncAccentPickerToThemeDefault();
            })
        );
        this.#addCleanup(this.#host.pageResources.on(getEventHub(), 'themeChanged', syncAccentPickerToThemeDefault));

        this.#addCleanup(
            this.#host.pageResources.on(accentControl.picker, 'input', () => {
                const normalized = colorController.readRequiredColor(accentControl, normalizeAccentColorPreference, 'Accent color picker value must be a valid hex color');
                const nextValue = normalized === readThemeDefaultAccent() ? null : normalized;
                this.#host.setUiPrefValue('accentColor', nextValue);
                colorController.setNullableColor(accentControl, nextValue, readThemeDefaultAccent());
            })
        );

        this.#addCleanup(
            this.#host.pageResources.on(accentControl.clearButton, 'click', () => {
                this.#host.setUiPrefValue('accentColor', null);
                colorController.clearNullableColor(accentControl, readThemeDefaultAccent());
            })
        );

        this.#addCleanup(
            this.#host.pageResources.on(surfaceControl.picker, 'input', () => {
                const normalized = colorController.readRequiredColor(surfaceControl, normalizeSurfaceColorPreference, 'Surface color picker value must be a valid hex color');
                this.#host.setUiPrefValue('surfaceColor', normalized);
                colorController.setNullableColor(surfaceControl, normalized, readSurfaceDefault());
            })
        );

        this.#addCleanup(
            this.#host.pageResources.on(surfaceControl.clearButton, 'click', () => {
                this.#host.setUiPrefValue('surfaceColor', null);
                colorController.clearNullableColor(surfaceControl, readSurfaceDefault());
            })
        );
    }

    #setupEffectsEventListeners(): void {
        const disableAnimationsToggle = narrowInput(this.#host.pageDom.requireHTMLElement('disable-animations-toggle'), 'Disable animations toggle');
        const glassEffectsToggle = narrowInput(this.#host.pageDom.requireHTMLElement('glass-effects-toggle'), 'Glass effects toggle');
        const animationOptionsPanel = this.#host.pageDom.requireHTMLElement('animation-options-panel');
        this.#projections.push(() => {
            const reduced = this.#host.getUiPrefValue('reduceMotions');
            const glass = this.#host.getUiPrefValue('glassEnabled');
            if (typeof reduced !== 'boolean' || typeof glass !== 'boolean') throw new TypeError('Theme effect preferences must be boolean');
            disableAnimationsToggle.checked = reduced;
            glassEffectsToggle.checked = glass;
            this.#updatePreferenceToggleLabel(disableAnimationsToggle, reduced);
            this.#updatePreferenceToggleLabel(glassEffectsToggle, glass);
            animationOptionsPanel.classList.toggle('u-hidden', reduced);
        });

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
