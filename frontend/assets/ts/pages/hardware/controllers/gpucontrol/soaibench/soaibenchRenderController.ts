/* SoAI - SoAI Bench GPU rendering controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/soaibench/soaibenchRenderController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DecodedSoAIBenchRun } from '@core/realtime/streammanager/resources/soaibenchRunsResource.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import { getSoAIBenchRunsForDevice, hasSoAIBenchHistoryForDevice, resolveSoAIBenchProfileLabel, resolveSoAIBenchStatusLabel } from '@features/hardware/public.ts';
import { hasPendingGpuApplyAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';
import type { GpuControlManagerDependencies, GpuUiState, SecurityService } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

interface SoAIBenchActionRenderContext {
    security: SecurityService;
    getIconSync: GpuControlManagerDependencies['getIconSync'];
}

type SoAIBenchPanelRun = {
    runId: string;
    profile: string;
    benchmarkMode: string;
    status: string;
    active: boolean;
    score: number | null;
};

type SoAIBenchActionId = 'hardware.gpu.soaibench.standard' | 'hardware.gpu.soaibench.stress' | 'hardware.gpu.soaibench.stop';

const esc = (value: string, security: SecurityService): string => security.escapeHtml(value);
const escAttr = (value: string, security: SecurityService): string => security.escapeAttribute(value);
const toText = (value: JsonValue | null | undefined): string => (isString(value) ? value.trim() : '');

const scoreFromRun = (run: DecodedSoAIBenchRun): number | null => {
    const overall = run.score?.overallScore;
    return isFiniteNumber(overall) ? overall : null;
};

const normalizeRun = (value: DecodedSoAIBenchRun): SoAIBenchPanelRun | null => {
    const runId = toText(value.runId);
    const profile = toText(value.profile);
    const status = toText(value.status);
    if (!runId || !profile || !status) {
        return null;
    }
    return {
        runId,
        profile,
        benchmarkMode: toText(value.benchmarkMode) || 'quick',
        status,
        active: value.active === true || status === 'running',
        score: scoreFromRun(value)
    };
};

const activeRunForDevice = (payload: JsonValue | null | undefined, deviceId: string): SoAIBenchPanelRun | null => {
    for (const value of getSoAIBenchRunsForDevice(payload, deviceId)) {
        const run = normalizeRun(value);
        if (!run) {
            continue;
        }
        if (run.active) {
            return run;
        }
    }
    return null;
};

const hasActiveSoAIBenchRunForDevice = (payload: JsonValue | null | undefined, deviceId: string | null): boolean => {
    return deviceId ? activeRunForDevice(payload, deviceId) !== null : false;
};

const hasActiveStressSoAIBenchRunForDevice = (payload: JsonValue | null | undefined, deviceId: string | null): boolean => {
    const run = deviceId ? activeRunForDevice(payload, deviceId) : null;
    return run?.profile === 'stress';
};

const formatRun = (run: SoAIBenchPanelRun): string => {
    if (run.profile === 'stress' && run.status === 'running') {
        return i18n.t('hardware.gpu.soaibench.stressRunningLabel');
    }
    const parts = [resolveSoAIBenchProfileLabel(run.profile), resolveSoAIBenchStatusLabel(run.status)];
    if (run.profile === 'standard' && run.benchmarkMode === 'certified') {
        parts.splice(1, 0, i18n.t('hardware.modals.soaibenchHistory.certification.certified'));
    }
    if (run.score !== null) {
        parts.push(String(Math.round(run.score)));
    }
    return parts.join(' - ');
};

const renderSoAIBenchActionButton = (context: SoAIBenchActionRenderContext, index: string, action: string, label: string, variant: string, disabled: boolean): string => {
    const labelAttr = escAttr(label, context.security);
    const gpuIndexAttr = escAttr(index, context.security);
    return `<button type="button" class="ui-button ui-button--sm ${variant} gpu-soaibench-btn" data-action="${escAttr(action, context.security)}" data-gpu-index="${gpuIndexAttr}" aria-label="${labelAttr}" data-tooltip="${labelAttr}"${disabled ? ' disabled' : ''}>${esc(label, context.security)}</button>`;
};

const resolveSoAIBenchActionLabel = (action: SoAIBenchActionId): string => {
    switch (action) {
        case 'hardware.gpu.soaibench.standard':
            return i18n.t('hardware.gpu.actions.soaibenchStandard');
        case 'hardware.gpu.soaibench.stress':
            return i18n.t('hardware.gpu.actions.soaibenchStress');
        case 'hardware.gpu.soaibench.stop':
            return i18n.t('hardware.gpu.actions.soaibenchStop');
    }
};

const renderSoAIBenchHistoryButton = (context: SoAIBenchActionRenderContext, index: string, state: GpuUiState, payload: JsonValue | null | undefined): string => {
    if (!hasSoAIBenchHistoryForDevice(payload, state.deviceId)) {
        return '';
    }
    const label = i18n.t('hardware.gpu.actions.soaibenchHistory');
    const labelAttr = escAttr(label, context.security);
    const gpuIndexAttr = escAttr(index, context.security);
    const historyIcon = context.getIconSync('clock', { size: 14, strokeWidth: 1.7 }).html;
    return `<button type="button" class="ui-round-button ui-round-button--neutral gpu-history-round-btn" data-action="hardware.gpu.soaibench.history" data-gpu-index="${gpuIndexAttr}" aria-label="${labelAttr}" data-tooltip="${labelAttr}"${state.pending ? ' disabled' : ''}>${historyIcon}</button>`;
};

const isSoAIBenchToggleDisabled = (state: GpuUiState): boolean => state.pending || state.saveMode || hasPendingGpuApplyAction(state);

const renderSoAIBenchToggleButton = (context: SoAIBenchActionRenderContext, index: string, state: GpuUiState): string => {
    const label = i18n.t('hardware.gpu.actions.test');
    const labelAttr = escAttr(label, context.security);
    const gpuIndexAttr = escAttr(index, context.security);
    const disabled = isSoAIBenchToggleDisabled(state);
    return `<button type="button" class="ui-button ui-button--sm ui-variant-primary gpu-test-btn" data-action="hardware.gpu.soaibench.toggle" data-gpu-index="${gpuIndexAttr}" aria-label="${labelAttr}" data-tooltip="${labelAttr}"${disabled ? ' disabled' : ''}>${esc(label, context.security)}</button>`;
};

const renderSoAIBenchActions = (context: SoAIBenchActionRenderContext, index: string, state: GpuUiState, payload: JsonValue | null | undefined): string => {
    const disabled = state.pending;
    const activeRun = state.soaibenchStopRequested ? null : state.deviceId ? activeRunForDevice(payload, state.deviceId) : null;
    if (activeRun?.profile === 'stress') {
        return renderSoAIBenchActionButton(context, index, 'hardware.gpu.soaibench.stop', resolveSoAIBenchActionLabel('hardware.gpu.soaibench.stop'), 'ui-variant-danger', disabled);
    }
    const startDisabled = disabled || activeRun !== null;
    const secondaryAction = activeRun !== null ? renderSoAIBenchActionButton(context, index, 'hardware.gpu.soaibench.stop', resolveSoAIBenchActionLabel('hardware.gpu.soaibench.stop'), 'ui-variant-danger', disabled) : renderSoAIBenchActionButton(context, index, 'hardware.gpu.soaibench.stress', resolveSoAIBenchActionLabel('hardware.gpu.soaibench.stress'), 'ui-variant-danger', startDisabled);
    return [renderSoAIBenchActionButton(context, index, 'hardware.gpu.soaibench.standard', resolveSoAIBenchActionLabel('hardware.gpu.soaibench.standard'), 'ui-variant-warning', startDisabled), secondaryAction].join('');
};

const renderSoAIBenchState = (context: SoAIBenchActionRenderContext, payload: JsonValue | null | undefined, index: string, state: GpuUiState): string => {
    if (!state.deviceId || state.soaibenchStopRequested) {
        return '';
    }
    const run = activeRunForDevice(payload, state.deviceId);
    if (!run) {
        return '';
    }
    const label = formatRun(run);
    const labelAttr = escAttr(label, context.security);
    const gpuIndexAttr = escAttr(index, context.security);
    if (run.profile === 'standard' && run.benchmarkMode === 'certified') {
        return `<button type="button" class="gpu-soaibench-state ui-status-badge warning" data-action="hardware.gpu.soaibench.reopen" data-gpu-index="${gpuIndexAttr}" data-soaibench-run-id="${escAttr(run.runId, context.security)}" aria-label="${labelAttr}" data-tooltip="${labelAttr}">${esc(label, context.security)}</button>`;
    }
    return `<span class="gpu-soaibench-state ui-status-badge warning" aria-label="${labelAttr}" data-tooltip="${labelAttr}">${esc(label, context.security)}</span>`;
};

export { hasActiveSoAIBenchRunForDevice, hasActiveStressSoAIBenchRunForDevice, isSoAIBenchToggleDisabled, renderSoAIBenchActions, renderSoAIBenchHistoryButton, renderSoAIBenchState, renderSoAIBenchToggleButton };
