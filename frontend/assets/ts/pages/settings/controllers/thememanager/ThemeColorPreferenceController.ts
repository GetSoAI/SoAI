/* SoAI - Settings page theme color preference controller [frontend/assets/ts/pages/settings/controllers/thememanager/ThemeColorPreferenceController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { narrowButton, narrowInput } from '@core/dom/narrowElement.ts';
import type { ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';

interface ThemeColorControl {
    picker: HTMLInputElement;
    clearButton: HTMLButtonElement;
}

interface ThemeColorControlLabels {
    picker: string;
    clearButton: string;
}

class ThemeColorPreferenceController {
    readonly #host: Pick<ThemeManagerHost, 'pageDom'>;

    constructor(host: Pick<ThemeManagerHost, 'pageDom'>) {
        this.#host = host;
    }

    requireControl(pickerSelector: string, clearButtonSelector: string, labels: ThemeColorControlLabels): ThemeColorControl {
        const picker = narrowInput(this.#host.pageDom.requireHTMLElement(pickerSelector), labels.picker);
        if (picker.type !== 'color') {
            throw new TypeError(`${labels.picker} must be type="color"`);
        }
        return {
            picker,
            clearButton: narrowButton(this.#host.pageDom.requireHTMLElement(clearButtonSelector), labels.clearButton)
        };
    }

    setNullableColor(control: ThemeColorControl, value: string | null, fallback: string): void {
        control.picker.value = value ?? fallback;
        ThemeColorPreferenceController.setClearButtonVisibility(control.clearButton, value !== null);
    }

    readRequiredColor(control: ThemeColorControl, normalize: (value: string) => string | null, errorMessage: string): string {
        const normalized = normalize(control.picker.value);
        if (!normalized) {
            throw new Error(errorMessage);
        }
        return normalized;
    }

    clearNullableColor(control: ThemeColorControl, fallback: string): void {
        control.picker.value = fallback;
        ThemeColorPreferenceController.setClearButtonVisibility(control.clearButton, false);
    }

    static setClearButtonVisibility(button: HTMLButtonElement, hasColor: boolean): void {
        dom.setVisibility(button, hasColor);
    }
}

export { ThemeColorPreferenceController };
