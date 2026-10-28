/* SoAI - Hardware page GPU control DOM controls [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlDomControls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyTextContent } from '@core/dom/textContent.ts';

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isFiniteNumber, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import { GPU_CONTROL_TYPES, GPU_CONTROLS_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { getDataAttribute, setDataAttribute } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/dom.ts';
import { isControlSupported, isGpuControlType } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';
import { getOffsetControlContext } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import { resolveClockDomain } from '@pages/hardware/controllers/gpucontrol/gpuClockDomain.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSnapshot, GpuSnapshotControl, GpuUiState, SliderElements } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

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

const getSupportedClockValues = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number, type: string): readonly JsonValue[] => {
    const capabilities = capabilitiesByIndex?.[String(index)];
    const clockInfo = type === 'core' ? capabilities?.coreClockMhz : type === 'memory' ? capabilities?.memClockMhz : null;
    if (!clockInfo) return [];
    const domain = resolveClockDomain(clockInfo);
    return domain.type === 'discrete' ? domain.values : [];
};

export const getSupportedSliderKeyboardValue = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number, type: string, slider: HTMLInputElement, key: string): number | null => {
    if (type !== 'core' && type !== 'memory') return null;
    if (!isControlSupported(capabilitiesByIndex, index, type, 'manual')) return null;
    let direction: number;
    if (key === 'ArrowLeft' || key === 'ArrowDown') direction = -1;
    else if (key === 'ArrowRight' || key === 'ArrowUp') direction = 1;
    else return null;
    if ((key === 'ArrowLeft' || key === 'ArrowRight') && getComputedStyle(slider).direction === 'rtl') direction *= -1;
    const offsetContext = getOffsetControlContext(capabilitiesByIndex, index, type);
    const current = readCoercedFiniteNumberOrNullValue(slider.value);
    const minimum = readCoercedFiniteNumberOrNullValue(slider.min);
    const maximum = readCoercedFiniteNumberOrNullValue(slider.max);
    if (current === null || minimum === null || maximum === null) return null;
    const defaultAbs = offsetContext?.defaultAbs ?? 0;
    const supportedValues = getSupportedClockValues(capabilitiesByIndex, index, type).flatMap((value) => {
        const absolute = readCoercedFiniteNumberOrNullValue(value);
        if (absolute === null) return [];
        const displayed = absolute - defaultAbs;
        return displayed >= minimum && displayed <= maximum ? [displayed] : [];
    });
    if (!supportedValues.length) return null;
    supportedValues.sort((firstValue, secondValue) => (firstValue - secondValue) * direction);
    return supportedValues.find((value) => (value - current) * direction > 0) ?? current;
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
    const valueInput = toggleLabel ? dom.resolve('.gpu-slider-value-input', toggleLabel) : null;
    const valueTrigger = toggleLabel ? dom.resolve('.ui-inline-text-edit__trigger', toggleLabel) : null;
    if (valueInput instanceof HTMLInputElement) result.valueInput = valueInput;
    if (valueTrigger instanceof HTMLButtonElement) result.valueTrigger = valueTrigger;
    if (container instanceof HTMLElement) result.container = container;
    return result;
};

export const getSliderSnapshot = (document: Document, capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number): GpuSnapshot => {
    const resolve = (currentTime: string): GpuSnapshotControl => {
        if (!isControlSupported(capabilitiesByIndex, index, currentTime)) {
            return { mode: 'auto', value: null };
        }
        const { slider, toggle } = getSliderElements(document, index, currentTime);
        if (!slider || !toggle) {
            throw new Error(`GPU control UI is missing for ${currentTime} (index ${String(index)})`);
        }
        const mode = readGpuControlFieldMode(slider, toggle);
        return { mode, value: mode === null ? null : readCoercedFiniteNumberOrNullValue(slider.value) };
    };
    const controlValues: Record<string, GpuSnapshotControl> = {};
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

export const readGpuControlFieldMode = (slider: HTMLInputElement, toggle: HTMLInputElement): GpuSnapshotControl['mode'] => {
    return getDataAttribute(slider, 'field-mode') === 'unknown' ? null : toggle.checked ? 'auto' : 'manual';
};

const updateSliderUi = (context: DomContext, index: string | number, type: string, isAuto: boolean, value: number | string): void => {
    if (!isControlSupported(context.capabilitiesByIndex, index, type)) {
        return;
    }
    const { slider, toggle, valueTrigger, container } = getSliderElements(context.document, index, type);
    if (!slider || !valueTrigger) {
        throw new Error(`GPU control UI is missing for ${type} (index ${String(index)})`);
    }
    setRangeValue(slider, str(value));
    setDataAttribute(slider, 'field-mode', isAuto ? 'auto' : 'manual');
    if (toggle && !isControlSupported(context.capabilitiesByIndex, index, type, isAuto ? 'manual' : 'auto')) toggle.disabled = true;
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
    applyTextContent(valueTrigger, label);
    valueTrigger.classList.toggle('u-ltr-inline', !isAuto);
};

export const setSliderToAuto = (context: DomContext, index: string | number, type: string, explicitDefault: string | number | null = null, { preserveManual = false }: { preserveManual?: boolean } = {}): void => {
    if (!isControlSupported(context.capabilitiesByIndex, index, type, 'auto')) {
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

export const setSliderToManual = (context: DomContext, index: string | number, type: string, manualValue: string | number | null = null, { alignToSupportedValue = true }: { alignToSupportedValue?: boolean } = {}): void => {
    if (!isControlSupported(context.capabilitiesByIndex, index, type, 'manual')) {
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

    if (alignToSupportedValue && isOffsetControl && numeric !== null && isFiniteNumber(offsetContext?.defaultAbs) && (type === 'core' || type === 'memory')) {
        const supportedClocks = getSupportedClockValues(context.capabilitiesByIndex, index, type);
        if (supportedClocks.length) {
            const defaultAbs = offsetContext.defaultAbs;
            const targetAbs = defaultAbs + numeric;
            const closestMhz = closestSupportedValue(supportedClocks, targetAbs) ?? defaultAbs;
            const snappedOffset = closestMhz - defaultAbs;
            if (isFiniteNumber(snappedOffset)) {
                raw = str(snappedOffset);
            }
        }
    } else if (alignToSupportedValue && numeric !== null && (type === 'core' || type === 'memory')) {
        raw = str(closestSupportedValue(getSupportedClockValues(context.capabilitiesByIndex, index, type), numeric) ?? numeric);
    } else if (alignToSupportedValue && numeric !== null && isObject(info) && Array.isArray(info['allowedValues'])) {
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
    const { slider, toggle, container } = getSliderElements(context.document, index, type);
    if (!slider || !toggle || !container) {
        throw new Error(`GPU control UI is missing for ${type} (index ${String(index)})`);
    }
    if (!isControlSupported(context.capabilitiesByIndex, index, type, isAuto ? 'auto' : 'manual')) {
        toggle.checked = container.classList.contains('gpu-slider-container--auto');
        return;
    }
    if (isAuto) {
        setSliderToAuto(context, index, type, getDataAttribute(slider, 'default'));
    } else {
        setSliderToManual(context, index, type, getDataAttribute(slider, 'last-manual'));
    }
};

export const markGpuStateHydrated = (ensureUiState: (index: string | number) => GpuUiState, index: string | number): void => {
    if (!isNullOrUndefined(index)) ensureUiState(index).previewHydrated = true;
};

export const resetGpuUiControls = (context: DomContext, index: string | number): void => {
    GPU_CONTROL_TYPES.forEach((currentTime: string) => {
        if (!isControlSupported(context.capabilitiesByIndex, index, currentTime, 'auto')) {
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
