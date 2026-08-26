/* SoAI - SoAI Bench GPU control effects [frontend/assets/ts/pages/hardware/controllers/gpucontrol/soaibench/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuOperationResponse, GpuSoAIBenchRun } from '@core/api/contracts/hardwareContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { HARDWARE_GPU_SOAIBENCH_RUNS } from '@core/realtime/streammanager/resources/ids.ts';
import { isString } from '@core/typeGuards.ts';
import type { ControlContext } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts';
import { resolveGpuDisplayIndex, resolveGpuDisplayName } from '@pages/hardware/controllers/gpucontrol/gpuDisplayLabelManager.ts';
import type { GpuSoAIBenchProfile, GpuSoAIBenchRunRecord, GpuSoAIBenchStartPayload } from '@pages/hardware/controllers/gpucontrol/soaibench/types.ts';

const str = String;

const refreshSoAIBenchRuns = async (context: ControlContext): Promise<void> => {
    const streamManager = await context.dependencies.resolveStreamManager();
    await streamManager.refresh(HARDWARE_GPU_SOAIBENCH_RUNS);
};

const resolveRunDeviceId = (run: GpuSoAIBenchRunRecord): string => {
    const identity = run.gpuIdentity;
    if (identity && isString(identity.deviceId)) {
        return identity.deviceId;
    }
    const direct = run.deviceId;
    return isString(direct) ? direct : '';
};

const findActiveRun = (runs: GpuSoAIBenchRun[] | undefined, deviceId: string): GpuSoAIBenchRunRecord | null => {
    if (!runs) {
        return null;
    }
    for (const value of runs) {
        const run = value;
        if (run.active !== true && run.status !== 'running') {
            continue;
        }
        if (resolveRunDeviceId(run) !== deviceId) {
            continue;
        }
        return run;
    }
    return null;
};

const resolveSoAIBenchUnsupportedReason = (result: GpuOperationResponse): string => {
    const reason = result.unsupportedReason || result.failureReason || result.status;
    if (isString(reason) && reason.trim()) {
        return reason.trim();
    }
    throw new Error('SoAIBench unsupported result requires a reason');
};

const notifySoAIBenchStartResult = (context: ControlContext, result: GpuOperationResponse, key: string, profile: GpuSoAIBenchProfile): void => {
    const displayIndex = resolveGpuDisplayIndex(context.capabilitiesByIndex, key);
    if (result.accepted) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.soaibenchStarted', { index: displayIndex, profile }), 'success');
        return;
    }
    const reason = resolveSoAIBenchUnsupportedReason(result);
    context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.soaibenchUnsupported', { index: displayIndex, reason }), result.status === 'unsupported' ? 'warning' : 'error');
};

const startPayloadForProfile = (profile: GpuSoAIBenchProfile): GpuSoAIBenchStartPayload => {
    return profile === 'standard' ? { profile, benchmarkMode: 'certified' } : { profile };
};

const startGpuSoAIBench = async (context: ControlContext, deviceId: string, index: string | number, profile: GpuSoAIBenchProfile): Promise<void> => {
    const key = str(index);
    const benchmarkMode = profile === 'standard' ? 'certified' : 'quick';
    const displayName = profile === 'stress' ? i18n.t('hardware.gpu.soaibench.stressTaskName') : i18n.t('hardware.gpu.soaibench.standardTaskName');
    await context.dependencies.runPageTask(
        `hardware.gpu.soaibench.${profile}`,
        async () => {
            const result = await context.dependencies.api.hardware.gpuSoAIBench.start(deviceId, startPayloadForProfile(profile));
            await refreshSoAIBenchRuns(context);
            notifySoAIBenchStartResult(context, result, key, profile);
        },
        {
            displayName,
            telemetryContext: { gpuIndex: key, profile, benchmarkMode },
            telemetryTags: ['hardware', 'gpu', 'soaibench'],
            throwOnError: true,
            notifyOnError: true
        }
    );
    context.syncSoAIBenchUi({ only: [key] });
};

const stopGpuSoAIBench = async (context: ControlContext, deviceId: string, index: string | number): Promise<void> => {
    const key = str(index);
    const displayIndex = resolveGpuDisplayIndex(context.capabilitiesByIndex, key);
    await context.dependencies.runPageTask(
        'hardware.gpu.soaibench.stop',
        async () => {
            const activeRuns = await context.dependencies.api.hardware.gpuSoAIBench.runs({ limit: 50 });
            const run = findActiveRun(activeRuns.runs, deviceId);
            const runId = run && isString(run.runId) ? run.runId : '';
            if (!runId) {
                context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.soaibenchNoActiveRun', { index: displayIndex }), 'info');
                return;
            }
            await context.dependencies.api.hardware.gpuSoAIBench.stop(runId);
            await refreshSoAIBenchRuns(context);
            context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.soaibenchStopRequested', { index: displayIndex }), 'success');
        },
        {
            displayName: i18n.t('hardware.gpu.soaibench.stopTaskName'),
            telemetryContext: { gpuIndex: key },
            telemetryTags: ['hardware', 'gpu', 'soaibench'],
            throwOnError: true,
            notifyOnError: true
        }
    );
    context.syncSoAIBenchUi({ only: [key] });
};

const showGpuSoAIBenchHistory = async (context: ControlContext, deviceId: string, index: string | number): Promise<void> => {
    await context.dependencies.showSoAIBenchHistory({
        deviceId,
        gpuIndex: resolveGpuDisplayIndex(context.capabilitiesByIndex, index),
        gpuName: resolveGpuDisplayName(context.capabilitiesByIndex, index)
    });
};

const showGpuSoAIBenchRun = async (context: ControlContext, deviceId: string, index: string | number): Promise<void> => {
    await context.dependencies.showSoAIBenchRun({
        deviceId,
        gpuIndex: resolveGpuDisplayIndex(context.capabilitiesByIndex, index),
        gpuName: resolveGpuDisplayName(context.capabilitiesByIndex, index)
    });
};

export { showGpuSoAIBenchHistory, showGpuSoAIBenchRun, startGpuSoAIBench, stopGpuSoAIBench };
