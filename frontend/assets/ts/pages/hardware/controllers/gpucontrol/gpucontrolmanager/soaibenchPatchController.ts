/* SoAI - SoAI Bench GPU patch controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/soaibenchPatchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createElementFromMarkup } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/dom.ts';
import type { GpuControlManagerViewContext } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/internalContracts.ts';
import { hasActiveSoAIBenchRunForDevice, hasActiveStressSoAIBenchRunForDevice, isSoAIBenchToggleDisabled, renderSoAIBenchActions, renderSoAIBenchHistoryButton, renderSoAIBenchState, renderSoAIBenchToggleButton } from '@pages/hardware/controllers/gpucontrol/soaibench/soaibenchRenderController.ts';

const keys = Object.keys;
const str = String;

const resolveGpuControlPanel = (container: HTMLElement, index: string): HTMLElement | null => {
    for (const element of dom.resolveAll('.gpu-control-panel', container)) {
        if (element instanceof HTMLElement && element.dataset['gpuIndex'] === index) {
            return element;
        }
    }
    return null;
};

const patchOptionalElement = (parent: HTMLElement, selector: string, markup: string, insertAfter: Element | null, insertBefore: Element | null = null): void => {
    const existing = dom.resolve(selector, parent);
    if (!markup) {
        existing?.remove();
        return;
    }
    const next = createElementFromMarkup(parent.ownerDocument, markup);
    if (existing) {
        if (existing.outerHTML === next.outerHTML) {
            return;
        }
        existing.replaceWith(next);
        return;
    }
    if (insertAfter) {
        insertAfter.after(next);
        return;
    }
    if (insertBefore) {
        insertBefore.before(next);
        return;
    }
    parent.appendChild(next);
};

const syncSoAIBenchStateBadge = (context: GpuControlManagerViewContext, panel: HTMLElement, index: string): void => {
    const header = dom.resolve('.gpu-control-header', panel);
    if (!(header instanceof HTMLElement)) {
        throw new Error(`GPU control header is missing for index ${index}`);
    }
    const title = dom.resolve('.gpu-control-title', header);
    const primaryActions = dom.resolve('.gpu-primary-actions', panel);
    if (!(primaryActions instanceof HTMLElement)) {
        throw new Error(`GPU control primary actions are missing for index ${index}`);
    }
    const primaryActionGroup = dom.resolve('.gpu-primary-action-group', primaryActions);
    if (!(primaryActionGroup instanceof HTMLElement)) {
        throw new Error(`GPU control primary action group is missing for index ${index}`);
    }
    const state = context.ensureUiState(index);
    const activeStressRun = !state.soaibenchStopRequested && hasActiveStressSoAIBenchRunForDevice(context.soaibenchRuns, state.deviceId);
    const markup = renderSoAIBenchState({ security: context.security, getIconSync: context.dependencies.getIconSync }, context.soaibenchRuns, index, state);
    patchOptionalElement(header, '.gpu-soaibench-state', activeStressRun ? '' : markup, title);
    patchOptionalElement(primaryActions, '.gpu-soaibench-state', activeStressRun ? markup : '', null, primaryActionGroup);
};

const syncSoAIBenchHistoryButton = (context: GpuControlManagerViewContext, panel: HTMLElement, index: string): void => {
    const actionBar = dom.resolve('.gpu-control-action-bar', panel);
    if (!(actionBar instanceof HTMLElement)) {
        throw new Error(`GPU control action bar is missing for index ${index}`);
    }
    const state = context.ensureUiState(index);
    const markup = renderSoAIBenchHistoryButton({ security: context.security, getIconSync: context.dependencies.getIconSync }, index, state, context.soaibenchRuns);
    patchOptionalElement(actionBar, '.gpu-history-round-btn', markup, dom.resolve('.gpu-reset-round-btn', actionBar));
};

const syncSoAIBenchActions = (context: GpuControlManagerViewContext, panel: HTMLElement, index: string): void => {
    const state = context.ensureUiState(index);
    const primaryActionGroup = dom.resolve('.gpu-primary-action-group', panel);
    if (!(primaryActionGroup instanceof HTMLElement)) {
        throw new Error(`GPU control primary action group is missing for index ${index}`);
    }
    const existingActions = dom.resolve('.gpu-soaibench-actions', primaryActionGroup);
    const existingToggle = dom.resolve('.gpu-test-btn', primaryActionGroup);
    const activeStressRun = !state.soaibenchStopRequested && hasActiveStressSoAIBenchRunForDevice(context.soaibenchRuns, state.deviceId);
    if (state.saveMode) {
        existingActions?.remove();
        existingToggle?.remove();
        return;
    }
    if ((state.showSoAIBenchActions && !isSoAIBenchToggleDisabled(state)) || activeStressRun) {
        const actionsMarkup = renderSoAIBenchActions({ security: context.security, getIconSync: context.dependencies.getIconSync }, index, state, context.soaibenchRuns);
        const actionsElement = createElementFromMarkup(primaryActionGroup.ownerDocument, `<div class="gpu-soaibench-actions">${actionsMarkup}</div>`);
        if (existingActions instanceof HTMLElement) {
            if (existingActions.outerHTML !== actionsElement.outerHTML) {
                existingActions.replaceWith(actionsElement);
            }
            return;
        }
        if (existingToggle instanceof HTMLElement) {
            existingToggle.replaceWith(actionsElement);
            return;
        }
        primaryActionGroup.appendChild(actionsElement);
        return;
    }
    const toggleMarkup = renderSoAIBenchToggleButton({ security: context.security, getIconSync: context.dependencies.getIconSync }, index, state);
    if (existingToggle instanceof HTMLElement) {
        existingToggle.replaceWith(createElementFromMarkup(primaryActionGroup.ownerDocument, toggleMarkup));
        return;
    }
    const toggleElement = createElementFromMarkup(primaryActionGroup.ownerDocument, toggleMarkup);
    if (existingActions instanceof HTMLElement) {
        existingActions.replaceWith(toggleElement);
        return;
    }
    primaryActionGroup.appendChild(toggleElement);
};

const syncGpuControlSoAIBenchUi = (context: GpuControlManagerViewContext, { only = null }: { only?: string[] | null } = {}): void => {
    const container = dom.resolve('#gpu-controls-container', context.dependencies.dom.getDocument());
    if (!(container instanceof HTMLElement)) {
        return;
    }
    const targets = only?.map(str).filter(Boolean) ?? keys(context.capabilitiesByIndex ?? {});
    targets.forEach((index) => {
        const panel = resolveGpuControlPanel(container, index);
        if (!panel) {
            return;
        }
        const state = context.ensureUiState(index);
        panel.classList.toggle('is-soaibench-stress-active', !state.soaibenchStopRequested && hasActiveStressSoAIBenchRunForDevice(context.soaibenchRuns, state.deviceId));
        if (state.soaibenchStopRequested && !hasActiveSoAIBenchRunForDevice(context.soaibenchRuns, state.deviceId)) {
            state.soaibenchStopRequested = false;
        }
        syncSoAIBenchStateBadge(context, panel, index);
        syncSoAIBenchHistoryButton(context, panel, index);
        syncSoAIBenchActions(context, panel, index);
    });
};

export { syncGpuControlSoAIBenchUi };
