/* SoAI - Hardware page GPU control manager rendering [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom, domCache } from '@core/dom/dom.ts';
import { replaceChildrenFromHtml } from '@core/dom/html.ts';
import { securityApi } from '@core/security/public.ts';
import { isArray } from '@core/typeGuards.ts';
import { GPU_CONTROL_TYPES, GPU_CONTROLS_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { createElementFromMarkup, getDataAttribute, setDataAttribute } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/dom.ts';
import { hasActionableGpuControls, isControlSupported } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';
import type { GpuControlManagerRendererContext, GpuControlManagerRenderPanelContext, GpuControlManagerViewContext, GpuControlSnapshotEntry, GpuControlViewSnapshot } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/internalContracts.ts';
import { getOffsetControlContext } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import { buildEmptyGpuControlsMarkup, renderGpuControlPanel } from '@pages/hardware/controllers/gpucontrol/gpuControlRenderer.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSettingKey } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const entries = Object.entries;
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

export const captureGpuControlsState = (context: GpuControlManagerViewContext): GpuControlViewSnapshot => {
    const state: GpuControlViewSnapshot = {};
    const container = dom.resolve('#gpu-controls-container');
    if (!(container instanceof HTMLElement)) {
        return state;
    }

    for (const panel of dom.resolveAll('.gpu-control-panel', container)) {
        if (!(panel instanceof HTMLElement)) {
            continue;
        }
        const index = panel.dataset['gpuIndex'];
        if (!index) {
            continue;
        }

        const controls: GpuControlSnapshotEntry['controls'] = {};
        GPU_CONTROL_TYPES.forEach((controlType) => {
            const { slider, toggle } = context.getSliderElements(index, controlType);
            if (!slider) {
                return;
            }
            if (!toggle) {
                throw new Error(`GPU control UI is missing for ${controlType} (index ${index})`);
            }

            controls[controlType] = {
                isAuto: toggle.checked,
                value: slider.value,
                lastManual: getDataAttribute(slider, 'last-manual')
            };
        });

        if (keys(controls).length) {
            state[index] = { deviceId: panel.dataset['deviceId'] ?? null, controls };
        }
    }

    return state;
};

const resolveSnapshotDestinationKey = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, snapshotKey: string, deviceId: string | null): string | null => {
    if (!capabilitiesByIndex) {
        return null;
    }
    if (capabilitiesByIndex[snapshotKey]) {
        return snapshotKey;
    }
    if (!deviceId) {
        return null;
    }
    const matches = keys(capabilitiesByIndex).filter((candidateKey) => capabilitiesByIndex[candidateKey]?.deviceId === deviceId);
    return matches.length === 1 ? (matches[0] ?? null) : null;
};

export const restoreGpuControlsState = (context: GpuControlManagerViewContext, snapshot: GpuControlViewSnapshot | null, restrictToKeys: ReadonlySet<string> | null = null): void => {
    if (!snapshot) {
        return;
    }

    entries(snapshot).forEach(([snapshotKey, gpuSnapshot]) => {
        const index = resolveSnapshotDestinationKey(context.capabilitiesByIndex, snapshotKey, gpuSnapshot.deviceId);
        if (!index || (restrictToKeys && !restrictToKeys.has(index))) {
            return;
        }

        entries(gpuSnapshot.controls).forEach(([controlType, controlSnapshot]) => {
            if (!isControlSupported(context.capabilitiesByIndex, index, controlType)) {
                return;
            }

            const { slider } = context.getSliderElements(index, controlType);
            if (!slider) {
                throw new Error(`GPU control UI is missing for ${controlType} (index ${index})`);
            }

            setDataAttribute(slider, 'last-manual', controlSnapshot.lastManual ?? '');
            if (controlSnapshot.isAuto) {
                context.setSliderToAuto(index, controlType, getDataAttribute(slider, 'default'), {
                    preserveManual: true
                });
            } else {
                context.setSliderToManual(index, controlType, controlSnapshot.value);
            }
        });
    });
};

export const renderGpuControls = (context: GpuControlManagerViewContext, { only = null }: { only?: string[] | null } = {}): void => {
    const document = context.dependencies.dom.getDocument();
    const container = dom.resolve('#gpu-controls-container');
    if (!(container instanceof HTMLElement)) {
        throw new Error('GPU controls container is missing');
    }

    const hasCapabilities = !!context.capabilitiesByIndex && keys(context.capabilitiesByIndex).length > 0;
    if (!hasCapabilities) {
        replaceChildrenFromHtml({
            element: container,
            html: securityApi.sanitizeHtml(
                buildEmptyGpuControlsMarkup({
                    security: context.security
                })
            ),
            context: container
        });
        return;
    }

    const targets = isArray(only)
        ? only
              .map(str)
              .filter(Boolean)
              .filter((index) => !!context.capabilitiesByIndex?.[index])
        : null;

    if (!targets || !targets.length) {
        const previousState = captureGpuControlsState(context);
        const capabilitiesByIndex = context.capabilitiesByIndex;
        if (!capabilitiesByIndex) {
            throw new Error('GPU capabilities are required to render GPU controls');
        }
        const actionableEntries = entries(capabilitiesByIndex).filter(([, caps]) => hasActionableGpuControls(caps));
        if (!actionableEntries.length) {
            replaceChildrenFromHtml({
                element: container,
                html: securityApi.sanitizeHtml(
                    buildEmptyGpuControlsMarkup({
                        security: context.security
                    })
                ),
                context: container
            });
            return;
        }

        const markup = actionableEntries.map(([index, caps]) => renderGpuControlPanelMarkup({ renderer: toRendererContext(context), index, caps })).join('');

        replaceChildrenFromHtml({ element: container, html: markup, context: container });
        restoreGpuControlsState(context, previousState);
        hydratePreviewStates(context);
        actionableEntries.forEach(([index]) => context.refreshApplyState(index));
        return;
    }

    const previousState = captureGpuControlsState(context);
    const refreshedTargets: string[] = [];

    targets.forEach((index) => {
        const caps = context.capabilitiesByIndex?.[index];
        const existing = resolveGpuControlPanel(container, index);
        if (!caps || !hasActionableGpuControls(caps)) {
            existing?.remove();
            return;
        }

        const markup = renderGpuControlPanelMarkup({ renderer: toRendererContext(context), index, caps }).trim();
        const next = createElementFromMarkup(document, markup);
        refreshedTargets.push(index);

        if (existing) {
            existing.replaceWith(next);
        } else {
            container.appendChild(next);
        }
    });

    domCache.invalidate('gpu-');
    restoreGpuControlsState(context, previousState, new Set(targets));
    hydratePreviewStates(context, targets);
    refreshedTargets.forEach((index) => context.refreshApplyState(index));
};

export const hydratePreviewStates = (context: GpuControlManagerViewContext, indices: string[] | null = null): void => {
    const targets = isArray(indices) ? indices : context.capabilitiesByIndex ? keys(context.capabilitiesByIndex) : [];

    targets.forEach((index) => {
        const caps = context.capabilitiesByIndex?.[index] ?? null;
        if (!caps || !hasActionableGpuControls(caps)) {
            return;
        }
        const state = context.ensureUiState(str(index));
        if (!state.previewSlot || !state.previewSettings || state.previewHydrated) {
            return;
        }

        entries(state.previewSettings).forEach(([settingKey, value]) => {
            if (!isGpuSettingKey(settingKey)) {
                return;
            }
            const setting = settingKey;
            const controlType = GPU_CONTROL_TYPES.find((candidate) => GPU_CONTROLS_CONFIG[candidate].settingKey === setting);
            if (!controlType) {
                return;
            }

            if (value.mode === 'auto') {
                context.setSliderToAuto(index, controlType);
            } else {
                const offsetContext = context.capabilitiesByIndex ? getOffsetControlContext(context.capabilitiesByIndex, index, controlType) : null;
                if (offsetContext && controlType !== 'fan') {
                    const abs = Number(value.value);
                    const offset = abs - offsetContext.defaultAbs;
                    context.setSliderToManual(index, controlType, offset);
                } else {
                    context.setSliderToManual(index, controlType, value.value ?? 0);
                }
            }
        });

        state.previewHydrated = true;
    });
};

export const renderGpuControlPanelMarkup = (context: GpuControlManagerRenderPanelContext): string => {
    return renderGpuControlPanel(
        {
            security: context.renderer.security,
            getIconSync: context.renderer.getIconSync,
            capabilitiesByIndex: context.renderer.capabilitiesByIndex,
            telemetryByDeviceId: context.renderer.telemetryByDeviceId,
            soaibenchRuns: context.renderer.soaibenchRuns,
            ensureUiState: (index) => context.renderer.ensureUiState(index)
        },
        context.index,
        context.caps
    );
};

const toRendererContext = (context: GpuControlManagerViewContext): GpuControlManagerRendererContext => {
    return {
        security: context.security,
        getIconSync: context.dependencies.getIconSync,
        capabilitiesByIndex: context.capabilitiesByIndex,
        telemetryByDeviceId: context.telemetryByDeviceId,
        soaibenchRuns: context.soaibenchRuns,
        ensureUiState: context.ensureUiState
    };
};

const isGpuSettingKey = (value: string): value is GpuSettingKey => {
    return value === 'powerLimit' || value === 'coreClock' || value === 'memClock' || value === 'fanSpeed';
};
