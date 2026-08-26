/* SoAI - Hardware page GPU control DOM controls [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlDomControls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isFiniteNumber, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import { GPU_CONTROL_TYPES, GPU_CONTROLS_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { getDataAttribute, setDataAttribute } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/dom.ts';
import { isControlSupported, isGpuControlType } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';
import { getOffsetControlContext } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSnapshot, GpuUiState, SliderElements } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const str = String;

type DomContext = {
    document: Document;
    capabilitiesByIndex: GpuCapabilitiesByIndex | null;
    ensureUiState: (index: string | number) => GpuUiState;
    refreshApplyState: (index: string | number) => void;
};

const setRangeValue = (slider: HTMLInputElement, value: string): void => {
    slider.value = value;
    slider.setAttribute('value', value);
};

const closestSupportedValue = (values: readonly JsonValue[], target: number): number | null => {
    let closest: number | null = null;
    let minimumDifference = Number.POSITIVE_INFINITY;
    values.forEach((value) => {
        const numeric = readCoercedFiniteNumberOrNullValue(value);
        if (numeric === null) return;
        const difference = Math.abs(numeric - target);
        if (difference < minimumDifference) {
            closest = numeric;
            minimumDifference = difference;
        }
    });
    return closest;
};

export const getSliderElements = (_document: Document, index: string | number, type: string): SliderElements => {
    const slider = dom.resolve(`#gpu-${index}-${type}-slider`);
    if (!(slider instanceof HTMLInputElement)) return {};
    const toggle = dom.resolve(`#gpu-${index}-${type}-auto`);
    const toggleInput = toggle instanceof HTMLInputElement ? toggle : null;
    const toggleContainer = toggleInput?.closest('.gpu-slider-auto-toggle');
    const toggleLabel = toggleContainer ? dom.resolve('.toggle-label', toggleContainer) : null;
    const valueLabel = dom.resolve(`#gpu-${index}-${type}-value`);
    const container = slider.closest('.gpu-slider-container');
    const result: SliderElements = { slider: slider };
    if (valueLabel instanceof HTMLElement) result.valueLabel = valueLabel;
    if (toggleInput) result.toggle = toggleInput;
    if (toggleLabel instanceof HTMLElement) result.toggleLabel = toggleLabel;
    if (container instanceof HTMLElement) result.container = container;
    return result;
};

export const getSliderSnapshot = (document: Document, capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number): GpuSnapshot => {
    const resolve = (currentTime: string): { mode: 'auto' | 'manual'; value: number | null } => {
        if (!isControlSupported(capabilitiesByIndex, index, currentTime)) {
            return { mode: 'auto', value: null };
        }
        const { slider, toggle } = getSliderElements(document, index, currentTime);
        if (!slider || !toggle) {
            throw new Error(`GPU control UI is missing for ${currentTime} (index ${String(index)})`);
        }
        return {
            mode: toggle.checked ? 'auto' : 'manual',
            value: readCoercedFiniteNumberOrNullValue(slider.value)
        };
    };
    const controlValues: Record<string, { mode: 'auto' | 'manual'; value: number | null }> = {};
    GPU_CONTROL_TYPES.forEach((currentTime) => {
        controlValues[currentTime] = resolve(currentTime);
    });
    return {
        power: controlValues['power'] ?? { mode: 'auto', value: null },
        core: controlValues['core'] ?? { mode: 'auto', value: null },
        memory: controlValues['memory'] ?? { mode: 'auto', value: null },
        fan: controlValues['fan'] ?? { mode: 'auto', value: null }
    };
};

const updateSliderUi = (context: DomContext, index: string | number, type: string, isAuto: boolean, value: number | string): void => {
    if (!isControlSupported(context.capabilitiesByIndex, index, type)) {
        return;
    }
    const { slider, toggleLabel, container } = getSliderElements(context.document, index, type);
    if (!slider || !toggleLabel) {
        throw new Error(`GPU control UI is missing for ${type} (index ${String(index)})`);
    }
    setRangeValue(slider, str(value));
    if (container) container.classList.toggle('gpu-slider-container--auto', isAuto);
    const unit = getDataAttribute(slider, 'unit');
    let label: string;
    if (isAuto) {
        label = i18n.t('hardware.gpu.controls.autoLabel');
    } else {
        const offsetContext = isGpuControlType(type) ? getOffsetControlContext(context.capabilitiesByIndex, index, type) : null;
        const isOffsetControl = !!offsetContext && type !== 'fan';
        if (isOffsetControl) {
            const numeric = readCoercedFiniteNumberOrNullValue(value);
            const sign = numeric !== null && numeric > 0 ? '+' : '';
            const suffix = unit ? ` ${unit}` : '';
            label = `${sign}${str(value)}${suffix}`;
        } else {
            label = `${value}${unit ? ` ${unit}` : ''}`;
        }
    }
    toggleLabel.textContent = label;
};

export const setSliderToAuto = (context: DomContext, index: string | number, type: string, explicitDefault: string | number | null = null, { preserveManual = false }: { preserveManual?: boolean } = {}): void => {
    if (!isControlSupported(context.capabilitiesByIndex, index, type)) {
        return;
    }
    const { slider, toggle } = getSliderElements(context.document, index, type);
    if (!slider || !toggle) {
        throw new Error(`GPU control UI is missing for ${type} (index ${String(index)})`);
    }
    const offsetContext = isGpuControlType(type) ? getOffsetControlContext(context.capabilitiesByIndex, index, type) : null;
    const isOffsetControl = !!offsetContext && type !== 'fan';
    const rawDefault = explicitDefault ?? getDataAttribute(slider, 'default') ?? slider.value;
    const nextValue = isOffsetControl ? 0 : rawDefault;
    if (!preserveManual) setDataAttribute(slider, 'last-manual', str(nextValue));
    toggle.checked = true;
    updateSliderUi(context, index, type, true, nextValue);
};

export const setSliderToManual = (context: DomContext, index: string | number, type: string, manualValue: string | number | null = null): void => {
    if (!isControlSupported(context.capabilitiesByIndex, index, type)) {
        return;
    }
    const { slider, toggle } = getSliderElements(context.document, index, type);
    if (!slider || !toggle) {
        throw new Error(`GPU control UI is missing for ${type} (index ${String(index)})`);
    }
    const offsetContext = isGpuControlType(type) ? getOffsetControlContext(context.capabilitiesByIndex, index, type) : null;
    const isOffsetControl = !!offsetContext && type !== 'fan';
    let raw = manualValue ?? getDataAttribute(slider, 'last-manual') ?? getDataAttribute(slider, 'default') ?? slider.value;
    const numeric = readCoercedFiniteNumberOrNullValue(raw);
    const caps = context.capabilitiesByIndex?.[String(index)];
    const capabilityKey = isGpuControlType(type) ? GPU_CONTROLS_CONFIG[type].capabilityKey : null;
    const info = capabilityKey ? caps?.[capabilityKey] : null;

    if (isOffsetControl && numeric !== null && isFiniteNumber(offsetContext?.defaultAbs) && (type === 'core' || type === 'memory')) {
        const levelsRaw = isObject(info) && 'levels' in info ? info['levels'] : null;
        if (Array.isArray(levelsRaw) && levelsRaw.length) {
            const defaultAbs = offsetContext.defaultAbs;
            const targetAbs = defaultAbs + numeric;
            const levelValues = levelsRaw.flatMap((entry) => (isObject(entry) ? [entry['mhz']] : []));
            const closestMhz = closestSupportedValue(levelValues, targetAbs) ?? defaultAbs;
            const snappedOffset = closestMhz - defaultAbs;
            if (isFiniteNumber(snappedOffset)) {
                raw = str(snappedOffset);
            }
        }
    } else if (numeric !== null && isObject(info) && Array.isArray(info['allowedValues'])) {
        raw = str(closestSupportedValue(info['allowedValues'], numeric) ?? numeric);
    }

    setDataAttribute(slider, 'last-manual', str(raw));
    toggle.checked = false;
    updateSliderUi(context, index, type, false, raw);
};

export const updateSliderAutoState = (context: DomContext, index: string | number, type: string, isAuto: boolean): void => {
    if (!isControlSupported(context.capabilitiesByIndex, index, type)) {
        return;
    }
    const { slider } = getSliderElements(context.document, index, type);
    if (!slider) {
        throw new Error(`GPU control UI is missing for ${type} (index ${String(index)})`);
    }
    if (isAuto) {
        setSliderToAuto(context, index, type, getDataAttribute(slider, 'default'), { preserveManual: true });
    } else {
        setSliderToManual(context, index, type, getDataAttribute(slider, 'last-manual'));
    }
};

export const markGpuStateHydrated = (ensureUiState: (index: string | number) => GpuUiState, index: string | number): void => {
    if (!isNullOrUndefined(index)) ensureUiState(index).previewHydrated = true;
};

export const resetGpuUiControls = (context: DomContext, index: string | number): void => {
    GPU_CONTROL_TYPES.forEach((currentTime: string) => {
        if (!isControlSupported(context.capabilitiesByIndex, index, currentTime)) {
            return;
        }
        const { slider } = getSliderElements(context.document, index, currentTime);
        if (!slider) {
            throw new Error(`GPU control UI is missing for ${currentTime} (index ${String(index)})`);
        }
        const defaultValue = getDataAttribute(slider, 'default');
        setDataAttribute(slider, 'last-manual', defaultValue ?? '');
        setSliderToAuto(context, index, currentTime, defaultValue);
    });
    markGpuStateHydrated(context.ensureUiState, index);
    context.refreshApplyState(index);
};
