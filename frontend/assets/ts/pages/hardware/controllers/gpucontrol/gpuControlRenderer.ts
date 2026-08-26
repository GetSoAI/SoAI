/* SoAI - Hardware page GPU control renderer [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { i18n } from '@core/i18n/index.ts';
import { isFiniteNumber, isNullOrUndefined } from '@core/typeGuards.ts';
import { GPU_CONTROLS_CONFIG, GPU_SLIDER_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { hasActionableGpuControls, isGpuCapabilityActionable } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';
import { resolveGpuControlLabel } from '@pages/hardware/controllers/gpucontrol/gpuControlLabelManager.ts';
import { getOffsetControlContext, normalizeGpuValue, settingStateToValue } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import { hasPendingGpuApplyAction, resolveGpuPrimaryAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';
import { formatGpuControlTelemetryLabel, resolveGpuControlTelemetryTemperatureSeverity, type GpuControlTelemetry } from '@pages/hardware/controllers/gpucontrol/gpuControlTelemetryController.ts';
import { renderGpuVendorLogo } from '@pages/hardware/controllers/gpucontrol/gpuControlVendorLogoController.ts';
import { hasActiveStressSoAIBenchRunForDevice, isSoAIBenchToggleDisabled, renderSoAIBenchActions, renderSoAIBenchHistoryButton, renderSoAIBenchState, renderSoAIBenchToggleButton } from '@pages/hardware/controllers/gpucontrol/soaibench/soaibenchRenderController.ts';
import type { GpuCapabilities, GpuCapabilitiesByIndex, GpuCapabilityControlInfo, GpuClockCapabilityInfo } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuControlManagerDependencies, GpuControlType, GpuControlValue, GpuSettingKey, GpuUiState, SecurityService } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const entries = Object.entries;
const str = String;

type RendererContext = {
    security: SecurityService;
    getIconSync: GpuControlManagerDependencies['getIconSync'];
    capabilitiesByIndex: GpuCapabilitiesByIndex | null;
    telemetryByDeviceId: Map<string, GpuControlTelemetry>;
    soaibenchRuns: JsonValue | null;
    ensureUiState: (index: string | number) => GpuUiState;
};

const esc = (value: string, sec: SecurityService): string => sec.escapeHtml(value);
const escAttr = (value: string, sec: SecurityService): string => sec.escapeAttribute(value);

const hasManualResettableControl = (state: GpuUiState, caps: GpuCapabilities): boolean => {
    return GPU_SLIDER_CONFIG.some(({ capabilityKey, type }) => {
        const info = caps[capabilityKey];
        if (!info || !isGpuCapabilityActionable(info)) {
            return false;
        }
        const settingKey = GPU_CONTROLS_CONFIG[type].settingKey;
        const setting = state.previewSettings?.[settingKey] ?? state.liveSettings?.[settingKey] ?? null;
        return setting?.mode === 'manual';
    });
};

export const renderGpuControlPanel = (context: RendererContext, index: string, caps: GpuCapabilities): string => {
    const state = context.ensureUiState(index);
    if (!hasActionableGpuControls(caps)) {
        return buildEmptyGpuControlsMarkup(context);
    }
    if (!state.deviceId && caps.deviceId) state.deviceId = caps.deviceId;
    const displayIndex = typeof caps.index === 'string' || typeof caps.index === 'number' ? String(caps.index) : index;
    const title = esc(
        i18n.t('hardware.gpu.panelHeader', {
            index: displayIndex,
            name: caps.name || i18n.t('common.unknown')
        }),
        context.security
    );
    const deviceAttr = state.deviceId ? ` data-device-id="${escAttr(state.deviceId, context.security)}"` : '';
    const pendingAttr = state.pending ? ' disabled="disabled"' : '';
    const applyDisabled = state.pending || !hasPendingGpuApplyAction(state);
    const applyText = i18n.t('hardware.gpu.actions.apply');
    const applyAttr = escAttr(applyText, context.security);
    const saveText = i18n.t('hardware.gpu.actions.save');
    const saveAttr = escAttr(saveText, context.security);
    const resetText = i18n.t('hardware.gpu.actions.reset');
    const resetAttr = escAttr(resetText, context.security);
    const gpuIndexAttr = escAttr(index, context.security);
    const checkerboard = resolveCheckerboardClass(Number(displayIndex));
    const resetVisible = hasManualResettableControl(state, caps);
    const resetIcon = context.getIconSync('refresh', { size: 14, strokeWidth: 1.7 }).html;
    const resetButton = `<button type="button" class="ui-round-button ui-round-button--delete gpu-reset-round-btn" data-action="hardware.gpu.reset" data-gpu-index="${gpuIndexAttr}" aria-label="${resetAttr}" data-tooltip="${resetAttr}"${pendingAttr}${resetVisible ? '' : ' u-hidden'}>${resetIcon}</button>`;
    const applyButton = `<button type="button" class="ui-button ui-button--sm ui-variant-accent gpu-apply-btn" id="gpu-${gpuIndexAttr}-apply" data-action="hardware.gpu.apply" data-gpu-index="${gpuIndexAttr}" aria-label="${applyAttr}" data-tooltip="${applyAttr}"${applyDisabled ? ' disabled' : ''}>${esc(applyText, context.security)}</button>`;
    const saveButton = `<button type="button" class="ui-button ui-button--sm ui-variant-accent gpu-save-btn" data-action="hardware.gpu.saveMode" data-gpu-index="${gpuIndexAttr}" data-save-mode="${state.saveMode ? 1 : 0}" aria-pressed="${state.saveMode}" aria-label="${saveAttr}" data-tooltip="${saveAttr}"${pendingAttr}>${esc(saveText, context.security)}</button>`;
    const activeStressRun = !state.soaibenchStopRequested && hasActiveStressSoAIBenchRunForDevice(context.soaibenchRuns, state.deviceId);
    const primaryAction = state.saveMode || resolveGpuPrimaryAction(state) === 'save' ? saveButton : applyButton;
    const testButton = renderSoAIBenchToggleButton(context, index, state);
    const testActions = state.saveMode ? '' : activeStressRun || (state.showSoAIBenchActions && !isSoAIBenchToggleDisabled(state)) ? `<div class="gpu-soaibench-actions">${renderSoAIBenchActions(context, index, state, context.soaibenchRuns)}</div>` : testButton;
    const slotButtons = activeStressRun ? renderSoAIBenchState(context, context.soaibenchRuns, index, state) : renderGpuSlotButtons(context, index, state);
    const historyButton = renderSoAIBenchHistoryButton(context, index, state, context.soaibenchRuns);
    return `<div class="gpu-control-panel ${checkerboard}${activeStressRun ? ' is-soaibench-stress-active' : ''}" data-gpu-index="${gpuIndexAttr}"${deviceAttr}><div class="gpu-control-header"><h4 class="gpu-control-title">${renderGpuVendorLogo(caps, context.security)}<span class="gpu-control-title-text">${title}</span></h4>${activeStressRun ? '' : renderSoAIBenchState(context, context.soaibenchRuns, index, state)}<div class="gpu-control-action-bar">${resetButton}${historyButton}</div></div><div class="gpu-control-body">${renderGpuSliders(context, index, caps)}<div class="gpu-control-actions"><div class="gpu-primary-actions">${slotButtons}<div class="gpu-primary-action-group">${primaryAction}${testActions}</div></div></div>${renderGpuBootToggle(context, index, state)}</div></div>`;
};

export const renderGpuSlotButtons = (context: RendererContext, index: string, state: GpuUiState): string => {
    const slots = state.slotMetadata?.slots ?? {};
    const gpuIndexAttr = escAttr(index, context.security);
    const buttons = [1, 2, 3]
        .map((slotNumber: number) => {
            const slotId = str(slotNumber);
            const slotData = slots[slotId];
            const has = !!slotData?.settings;
            const cl = ['ui-button', 'ui-button--sm', 'gpu-slot-button'];
            if (!has) cl.push('gpu-slot-button--empty');
            if (state.saveMode) cl.push('is-flashing');
            if (has) {
                cl.push('gpu-slot-button--filled');
                if (state.activeSlot === slotId) cl.push('gpu-slot-button--active');
                if (state.previewSlot === slotId) cl.push('gpu-slot-button--preview');
                if (state.bootSlot === slotId) cl.push('gpu-slot-button--boot');
            }
            const dis = state.pending || (!state.saveMode && !has);
            const tooltipTextRaw = !has ? i18n.t('hardware.gpu.slots.emptyTooltip', { slot: slotId }) : state.saveMode ? i18n.t('hardware.gpu.slots.saveTooltip', { slot: slotId }) : i18n.t('hardware.gpu.slots.previewTooltip', { slot: slotId });
            const tooltipText = esc(tooltipTextRaw, context.security);
            const slotIdAttr = escAttr(slotId, context.security);
            const label = esc(i18n.t('hardware.gpu.slots.buttonLabel', { slot: slotId }), context.security);
            return `<button type="button" class="${cl.join(' ')}" data-action="hardware.gpu.slot" data-gpu-index="${gpuIndexAttr}" data-slot-id="${slotIdAttr}" aria-label="${tooltipText}" data-tooltip="${tooltipText}"${dis ? ' disabled' : ''}>${label}</button>`;
        })
        .join('');
    return `<div class="gpu-slot-group">${buttons}</div>`;
};

export const renderGpuBootToggle = (context: RendererContext, index: string, state: GpuUiState): string => {
    const deviceId = state.deviceId;
    const telemetry = deviceId ? (context.telemetryByDeviceId.get(str(deviceId)) ?? null) : null;
    const telemetryLabel = formatGpuControlTelemetryLabel(telemetry);
    const hasTelemetry = telemetryLabel.length > 0;
    const severity = resolveGpuControlTelemetryTemperatureSeverity(telemetry);
    const severityClass = hasTelemetry && severity !== 'normal' ? ` gpu-boot-telemetry--${severity}` : '';
    const gpuIndexAttr = escAttr(index, context.security);
    const deviceAttr = deviceId ? ` data-device-id="${escAttr(deviceId, context.security)}"` : '';
    const telemetrySpan = `<span class="gpu-boot-telemetry${severityClass}${hasTelemetry ? '' : ' gpu-boot-telemetry--hidden'}"${deviceAttr} data-gpu-index="${gpuIndexAttr}" aria-hidden="${hasTelemetry ? 'false' : 'true'}">${esc(telemetryLabel, context.security)}</span>`;
    const applyAtBootText = i18n.t('hardware.gpu.slots.apply_at_boot');
    const labelText = esc(applyAtBootText, context.security);
    const labelAttr = escAttr(applyAtBootText, context.security);
    const dis = state.pending || !state.previewSlot;
    const checked = !!(state.previewSlot && state.applyAtBootDesired);
    const bootTooltipText = escAttr(i18n.t('hardware.gpu.slots.applyAtBootTooltip'), context.security);
    const toggleInner = `<label class="toggle-switch" data-tooltip="${bootTooltipText}" for="gpu-boot-toggle-${gpuIndexAttr}"><input type="checkbox" id="gpu-boot-toggle-${gpuIndexAttr}" class="gpu-boot-toggle" data-action="hardware.gpu.boot.toggle" data-gpu-index="${gpuIndexAttr}" aria-label="${labelAttr}"${checked ? ' checked' : ''}${dis ? ' disabled' : ''}><span class="slider"></span></label><span class="gpu-boot-toggle-label">${labelText}</span>`;
    const containerClass = `gpu-boot-toggle-container${state.previewSlot ? '' : ' gpu-boot-toggle-container--reserved'}`;
    return `<div class="gpu-boot-toggle-row" data-gpu-index="${gpuIndexAttr}">${telemetrySpan}<div class="${containerClass}" aria-hidden="${state.previewSlot ? 'false' : 'true'}">${toggleInner}</div></div>`;
};

export const renderGpuSliders = (context: RendererContext, index: string, caps: GpuCapabilities): string => {
    return `<div class="gpu-sliders">${GPU_SLIDER_CONFIG.map(({ capabilityKey, type }) => {
        const info = caps[capabilityKey];
        return info ? renderSlider(context, index, type, info) : '';
    }).join('')}</div>`;
};

export const renderSlider = (context: RendererContext, index: string, type: GpuControlType, info: GpuCapabilityControlInfo | GpuClockCapabilityInfo): string => {
    const state = context.ensureUiState(index);
    const config = GPU_CONTROLS_CONFIG[type];
    const { unit, settingKey } = config;
    const supported = isGpuCapabilityActionable(info);
    if (!supported) {
        return '';
    }
    const offsetContext = type === 'fan' ? null : getOffsetControlContext(context.capabilitiesByIndex, index, type);
    const isOffsetControl = !!offsetContext && type !== 'fan';

    let min: number;
    let max: number;
    let step: number = 1;
    if ('step' in info && Number.isFinite(Number(info.step))) step = Number(info.step);
    if (step <= 0 && 'ticks' in info && Number.isFinite(Number(info.ticks))) step = Number(info.ticks);
    if (!Number.isFinite(step) || step <= 0) step = 1;

    let defaultValue: number;
    let currentValue: number;
    let defaultAbs: number | null = null;

    if (isOffsetControl && offsetContext) {
        min = offsetContext.offsetMin;
        max = offsetContext.offsetMax;
        defaultAbs = offsetContext.defaultAbs;
        const currentAbsRaw = 'current' in info ? info.current : undefined;
        const valueAbsRaw = 'value' in info ? info.value : undefined;
        const currentAbsCandidate = Number(currentAbsRaw ?? valueAbsRaw ?? defaultAbs);
        let currentOffset = isFiniteNumber(currentAbsCandidate) && isFiniteNumber(defaultAbs) ? currentAbsCandidate - defaultAbs : 0;
        if (!isFiniteNumber(currentOffset)) currentOffset = 0;
        if (currentOffset < min) currentOffset = min;
        if (currentOffset > max) currentOffset = max;
        defaultValue = 0;
        currentValue = currentOffset;
    } else {
        const capability = isControlCapabilityInfo(info) ? info : {};
        min = Number(capability.min ?? capability.minimum ?? 0);
        max = Number(capability.max ?? capability.maximum ?? min);
        defaultValue = Number(capability.default ?? min);
        currentValue = Number(capability.current ?? capability.value ?? defaultValue);
    }

    const previewState = supported && state.previewSettings ? state.previewSettings[settingKey] : null;
    const liveState = supported && state.liveSettings ? state.liveSettings[settingKey] : null;
    const previewValue = settingStateToValue(previewState);
    const liveValue = settingStateToValue(liveState);
    const isAuto = previewState ? previewState.mode === 'auto' : liveState ? liveState.mode === 'auto' : true;

    let sliderValue: number;
    let lastManual: number;

    if (isOffsetControl) {
        if (!isFiniteNumber(defaultAbs)) {
            throw new Error(`GPU offset defaults are required for ${type} (index ${index})`);
        }
        const targetAbs = previewValue !== 'auto' ? Number(previewValue) : liveValue !== 'auto' ? Number(liveValue) : defaultAbs + currentValue;
        let targetOffset = isFiniteNumber(targetAbs) ? targetAbs - defaultAbs : 0;
        if (!isFiniteNumber(targetOffset)) targetOffset = 0;
        if (targetOffset < min) targetOffset = min;
        if (targetOffset > max) targetOffset = max;
        sliderValue = isAuto ? 0 : targetOffset;
        lastManual = targetOffset;
    } else {
        const resolvedCurrent = isFiniteNumber(currentValue) ? currentValue : defaultValue;
        let manualValue = resolvedCurrent;
        if (previewValue !== 'auto') {
            manualValue = Number(previewValue);
        } else if (liveValue !== 'auto') {
            manualValue = Number(liveValue);
        }
        sliderValue = isAuto ? defaultValue : manualValue;
        lastManual = manualValue;
    }

    const formatLabel = (): string => {
        if (isAuto) return i18n.t('hardware.gpu.controls.autoLabel');
        if (isOffsetControl) {
            const numeric = Number(sliderValue);
            const sign = numeric > 0 ? '+' : '';
            const suffix = unit ? ` ${unit}` : '';
            return `${sign}${numeric}${suffix}`;
        }
        return `${sliderValue}${unit ? ` ${unit}` : ''}`;
    };

    const formatted = formatLabel();
    const labelText = unit ? `${resolveGpuControlLabel(type)} (${unit})` : resolveGpuControlLabel(type);
    const label = esc(labelText, context.security);
    const toggleTooltip = esc(i18n.t('hardware.gpu.controls.toggleAutomatic'), context.security);

    const attrs = (objectValue: Record<string, JsonValue | undefined>): string =>
        entries(objectValue)
            .filter(([, value]) => !isNullOrUndefined(value))
            .map(([key, value]) => `${key}="${escAttr(String(value), context.security)}"`)
            .join(' ');

    const sliderAttrs: Record<string, JsonValue | undefined> = {
        id: `gpu-${index}-${type}-slider`,
        type: 'range',
        class: 'gpu-slider',
        'data-action': 'hardware.gpu.slider.input',
        'data-gpu-index': index,
        'data-slider-type': type,
        'data-unit': unit,
        min,
        max,
        step,
        value: sliderValue,
        'data-last-manual': lastManual,
        'data-default': isOffsetControl ? 0 : defaultValue,
        disabled: undefined
    };

    const toggleLabelText = isAuto ? i18n.t('hardware.gpu.controls.autoLabel') : formatted;
    const toggleLabel = esc(toggleLabelText, context.security);
    const valueLabel = esc(formatted, context.security);

    return `<div class="gpu-slider-container setting-change-surface${isAuto ? ' gpu-slider-container--auto' : ''}"><div class="gpu-slider-header"><label class="gpu-slider-label" for="gpu-${index}-${type}-slider">${label}</label><label class="toggle-switch gpu-slider-auto gpu-slider-auto-toggle" for="gpu-${index}-${type}-auto" data-tooltip="${toggleTooltip}"><input ${attrs({ id: `gpu-${index}-${type}-auto`, type: 'checkbox', class: 'gpu-slider-auto-input', 'data-action': 'hardware.gpu.slider.auto', 'data-gpu-index': index, 'data-slider-type': type, 'aria-label': toggleTooltip, checked: isAuto ? 'checked' : undefined, disabled: undefined })}><span class="slider"></span><span class="toggle-label">${toggleLabel}</span></label></div><div class="gpu-slider-body"><input ${attrs(sliderAttrs)}><span class="gpu-slider-value" id="gpu-${index}-${type}-value">${valueLabel}</span></div></div>`;
};

const isControlCapabilityInfo = (value: GpuCapabilityControlInfo | GpuClockCapabilityInfo): value is GpuCapabilityControlInfo => {
    return 'min' in value || 'max' in value || 'ticks' in value || 'step' in value;
};

export const buildEmptyGpuControlsMarkup = (context: Pick<RendererContext, 'security'>): string => `<p class="hardware-placeholder-text">${esc(i18n.t('hardware.cards.gpu.noControls'), context.security)}</p>`;

export const normalizeSettingValue = (value: JsonValue): GpuControlValue => (value === 'auto' ? 'auto' : normalizeGpuValue(value));

export const getSettingKeyForControl = (controlType: GpuControlType): GpuSettingKey => GPU_CONTROLS_CONFIG[controlType].settingKey;
