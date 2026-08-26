/* SoAI - Shared UI color toolkit base [frontend/assets/ts/core/ui/colorToolkitBase.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

type ColorValueInput = string | number | boolean | null | undefined;

interface ColorOption {
    value: string;
    key: string;
}

interface ColorGroup {
    value: string | null;
    key: string;
}

type ColorKey = 'none' | 'red' | 'yellow' | 'purple' | 'green' | 'blue';

interface ColorToolkitHost {
    queryUI(selector: string, container?: Element): Element[];
    toggleClassName(element: Element, className: string, force: boolean): void;
    optionalUI(selector: string, container?: Element): Element | null;
    dom: { getDocument(): Document };
}

const COLOR_VALUES: Readonly<string[]> = Object.freeze(['Red', 'Yellow', 'Purple', 'Green', 'Blue']);
const COLOR_OPTIONS: Readonly<ColorOption[]> = Object.freeze(
    COLOR_VALUES.map((value) => ({
        value,
        key: value.toLowerCase()
    }))
);
const COLOR_GROUPS: Readonly<ColorGroup[]> = Object.freeze([{ value: null, key: 'none' }, ...COLOR_OPTIONS]);
const COLOR_LOOKUP: Map<string, string> = new Map(COLOR_OPTIONS.map((option) => [option.value.toLowerCase(), option.value]));

const normalizeColor = (value: ColorValueInput): string | null => {
    if (isNullOrUndefined(value)) return null;
    const raw = String(value).trim();
    if (!raw) return null;
    const match = COLOR_LOOKUP.get(raw.toLowerCase());
    return match || null;
};

const validateColorToolkitHost = (host: ColorToolkitHost, errorMessage: string): void => {
    if (!host) {
        throw new Error(errorMessage);
    }
    if (!isFunction(host.queryUI)) {
        throw new Error(errorMessage);
    }
    if (!isFunction(host.toggleClassName)) {
        throw new Error(errorMessage);
    }
    if (!isFunction(host.optionalUI)) {
        throw new Error(errorMessage);
    }
    if (!host.dom || !isFunction(host.dom.getDocument)) {
        throw new Error(errorMessage);
    }
};

interface ColorToolkitConfig {
    cssPrefix: string;
    pickerClassName: string;
    selectActionName: string;
    dataAttributeName: string;
    resolvePickerLabel: () => string;
    resolveOptionLabel: (key: ColorKey) => string;
    errorMessage: string;
}

class BaseColorToolkit {
    protected host: ColorToolkitHost;
    protected config: ColorToolkitConfig;
    readonly groups: Readonly<ColorGroup[]> = COLOR_GROUPS;

    constructor(host: ColorToolkitHost, config: ColorToolkitConfig) {
        validateColorToolkitHost(host, config.errorMessage);
        this.host = host;
        this.config = config;
    }

    normalize(value: ColorValueInput): string | null {
        return normalizeColor(value);
    }

    resolveKey(colorValue: ColorValueInput): ColorKey {
        const normalized = this.normalize(colorValue);
        const defaultGroup = COLOR_GROUPS[0];
        if (!defaultGroup) {
            throw new Error('Color groups must not be empty');
        }
        const option = normalized ? COLOR_OPTIONS.find((candidate) => candidate.value === normalized) : defaultGroup;
        const key = option ? option.key : defaultGroup.key;
        if (key === 'none' || key === 'red' || key === 'yellow' || key === 'purple' || key === 'green' || key === 'blue') {
            return key;
        }
        throw new Error(`Unhandled color key: ${key}`);
    }

    getLabel(colorValue: ColorValueInput): string {
        return this.config.resolveOptionLabel(this.resolveKey(colorValue));
    }

    renderPicker(selectedColor: ColorValueInput): HTMLDivElement {
        const normalized = this.normalize(selectedColor);
        const documentRef = this.host.dom.getDocument();
        const picker = documentRef.createElement('div');
        picker.className = this.config.pickerClassName;
        picker.setAttribute('role', 'radiogroup');
        picker.setAttribute('aria-label', this.config.resolvePickerLabel());
        COLOR_GROUPS.forEach((option) => {
            const isSelected = option.value === null ? normalized === null : normalized === option.value;
            const button = documentRef.createElement('button');
            button.type = 'button';
            const classes = [`${this.config.cssPrefix}-option`, `${this.config.cssPrefix}-option-${option.key}`];
            if (isSelected) {
                classes.push('is-selected');
            }
            button.className = classes.join(' ');
            button.dataset['action'] = this.config.selectActionName;
            button.dataset['color'] = option.value ?? '';
            const optionKey = this.resolveKey(option.value);
            const label = this.config.resolveOptionLabel(optionKey);
            button.setAttribute('aria-label', label);
            setTooltipText(button, label);
            button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
            picker.appendChild(button);
        });
        return picker;
    }

    updatePicker(container: Element | null | undefined, selectedColor: ColorValueInput): void {
        if (!container) return;
        if (!(container instanceof HTMLElement)) {
            throw new Error(`${this.config.errorMessage}: expected HTMLElement container for picker update`);
        }
        const normalized = this.normalize(selectedColor);
        container.dataset['selectedColor'] = normalized ?? '';
        const buttons = this.host.queryUI(`.${this.config.cssPrefix}-option`, container);
        buttons.forEach((button) => {
            if (!(button instanceof HTMLElement)) {
                throw new Error(`${this.config.errorMessage}: expected HTMLElement button in picker update`);
            }
            const candidate = this.normalize(button.dataset['color']);
            const isSelected = normalized === null ? candidate === null : candidate === normalized;
            this.host.toggleClassName(button, 'is-selected', isSelected);
            button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
        });
    }
}

export { COLOR_VALUES, COLOR_OPTIONS, COLOR_GROUPS, COLOR_LOOKUP, normalizeColor, validateColorToolkitHost, BaseColorToolkit };
export type { ColorKey, ColorOption, ColorGroup, ColorToolkitHost, ColorToolkitConfig, ColorValueInput };
