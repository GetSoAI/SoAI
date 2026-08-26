/* SoAI - Prompt color toolkit [frontend/assets/ts/features/prompts/colorToolkit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { BaseColorToolkit, COLOR_GROUPS, COLOR_OPTIONS, COLOR_VALUES, type ColorKey, type ColorToolkitConfig, type ColorToolkitHost, type ColorValueInput } from '@core/ui/colorToolkitBase.ts';

const PROMPTS_ACTION_COLOR_SELECT = 'prompts.colorSelect';

const PROMPTS_COLOR_CONFIG: ColorToolkitConfig = {
    cssPrefix: 'prompt-color',
    pickerClassName: 'prompt-color-picker',
    selectActionName: PROMPTS_ACTION_COLOR_SELECT,
    dataAttributeName: 'promptColor',
    resolvePickerLabel: () => i18n.t('prompts.colors.pickerLabel'),
    resolveOptionLabel: (key: ColorKey): string => {
        switch (key) {
            case 'none':
                return i18n.t('prompts.colors.none');
            case 'red':
                return i18n.t('prompts.colors.red');
            case 'yellow':
                return i18n.t('prompts.colors.yellow');
            case 'purple':
                return i18n.t('prompts.colors.purple');
            case 'green':
                return i18n.t('prompts.colors.green');
            case 'blue':
                return i18n.t('prompts.colors.blue');
        }
    },
    errorMessage: 'Prompts color toolkit requires host'
};

class ColorToolkit extends BaseColorToolkit {
    constructor(host: ColorToolkitHost) {
        super(host, PROMPTS_COLOR_CONFIG);
    }

    override renderPicker(selectedColor: ColorValueInput, context: string = 'card'): HTMLDivElement {
        const picker = super.renderPicker(selectedColor);
        picker.dataset['colorContext'] = context;
        return picker;
    }

    override updatePicker(container: Element | null | undefined, selectedColor: ColorValueInput): void {
        if (!container) return;
        const normalized = this.normalize(selectedColor);
        if (!(container instanceof HTMLElement)) {
            throw new TypeError('Color picker container must be an HTMLElement');
        }
        container.dataset['selectedColor'] = normalized ?? '';
        const buttons = this.host.queryUI('.prompt-color-option', container);
        buttons.forEach((button) => {
            if (!(button instanceof HTMLElement)) {
                throw new TypeError('Color picker button must be an HTMLElement');
            }
            const candidate = this.normalize(button.dataset['color']);
            const isSelected = normalized === null ? candidate === null : candidate === normalized;
            this.host.toggleClassName(button, 'is-selected', isSelected);
            button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
        });
    }

    applyToCard(card: HTMLElement | null | undefined, colorValue: ColorValueInput): void {
        if (!card) return;
        const normalized = this.normalize(colorValue);
        const picker = this.host.optionalUI('.prompt-color-picker', card);
        if (picker) {
            this.updatePicker(picker, normalized);
        }
        card.dataset['selectedColor'] = normalized ?? '';
        if (normalized) {
            card.dataset['promptColor'] = normalized;
        } else {
            delete card.dataset['promptColor'];
        }
    }

    applyToModal(modal: HTMLElement, colorValue: ColorValueInput): void {
        if (!(modal instanceof HTMLElement)) {
            throw new TypeError('Prompt modal root must be an HTMLElement');
        }
        const normalized = this.normalize(colorValue);
        modal.dataset['selectedColor'] = normalized ?? '';
        if (normalized) {
            modal.dataset['promptColor'] = normalized;
        } else {
            delete modal.dataset['promptColor'];
        }
        const picker = this.host.optionalUI('.prompt-color-picker', modal);
        if (picker) {
            this.updatePicker(picker, normalized);
        }
    }
}

export { COLOR_GROUPS, COLOR_OPTIONS, COLOR_VALUES, ColorToolkit, PROMPTS_ACTION_COLOR_SELECT };
