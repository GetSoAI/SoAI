/* SoAI - Hardware feature SoAI Bench labels [frontend/assets/ts/features/hardware/soaibenchLabels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatSentenceLabelFromId } from '@core/primitives/text.ts';

const notAvailable = (): string => i18n.t('common.notAvailableShort');

interface SoAIBenchDeadline {
    failedPhase: string | null;
    deadlineSeconds: number | null;
}

const resolveSoAIBenchPhaseLabel = (phase: string | null): string | null => {
    if (phase === 'compute') return i18n.t('hardware.modals.soaibenchRun.phases.compute');
    if (phase === 'alu') return i18n.t('hardware.modals.soaibenchRun.phases.alu');
    if (phase === 'matrix') return i18n.t('hardware.modals.soaibenchRun.phases.matrix');
    if (phase === 'latency') return i18n.t('hardware.modals.soaibenchRun.phases.latency');
    if (phase === 'memory') return i18n.t('hardware.modals.soaibenchRun.phases.memory');
    if (phase === 'mixed' || phase === 'stability') return i18n.t('hardware.modals.soaibenchRun.phases.stability');
    return null;
};

const resolveDeadlineReason = (failureReason: string | null, deadline: SoAIBenchDeadline | null): string | null => {
    if (failureReason !== 'opencl_phase_deadline' && failureReason !== 'opencl_preflight_deadline' && failureReason !== 'opencl_startup_deadline' && failureReason !== 'opencl_runtime_deadline') return null;
    const seconds = deadline?.deadlineSeconds;
    const phase = failureReason === 'opencl_preflight_deadline' ? i18n.t('hardware.modals.soaibenchHistory.reasons.preflight') : failureReason === 'opencl_startup_deadline' ? i18n.t('hardware.modals.soaibenchHistory.reasons.startup') : resolveSoAIBenchPhaseLabel(deadline?.failedPhase ?? null);
    return phase !== null && seconds !== null && seconds !== undefined && Number.isFinite(seconds) && seconds > 0 ? i18n.t('hardware.errors.opencl_operation_deadline', { phase, seconds }) : i18n.t('hardware.errors.opencl_runtime_deadline');
};

const formatUnexpectedSoAIBenchIdentifierLabel = (value: string | null): string => {
    if (!value) {
        return notAvailable();
    }
    if (/^[a-z0-9_]+$/i.test(value)) {
        return formatSentenceLabelFromId(value);
    }
    return value;
};

const resolveSoAIBenchProfileLabel = (value: string | null): string => {
    if (!value) {
        return notAvailable();
    }
    switch (value) {
        case 'standard':
            return i18n.t('hardware.modals.soaibenchHistory.profiles.standard');
        case 'stress':
            return i18n.t('hardware.modals.soaibenchHistory.profiles.stress');
        default:
            return formatUnexpectedSoAIBenchIdentifierLabel(value);
    }
};

const resolveSoAIBenchStatusLabel = (value: string | null): string => {
    if (!value) {
        return notAvailable();
    }
    switch (value) {
        case 'running':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.running');
        case 'completed':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.completed');
        case 'unstable':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.unstable');
        case 'failed':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.failed');
        case 'cancelled':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.cancelled');
        case 'stopped':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.stopped');
        case 'unsupported':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.unsupported');
        case 'indeterminate':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.indeterminate');
        default:
            return formatUnexpectedSoAIBenchIdentifierLabel(value);
    }
};

const resolveSoAIBenchMatchBasisLabel = (value: string | null): string => {
    if (!value) {
        return notAvailable();
    }
    switch (value) {
        case 'device_id':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.device_id');
        case 'gpu_uuid':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.gpu_uuid');
        case 'pci_bdf':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.pci_bdf');
        case 'gpu_model_key':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.gpu_model_key');
        case 'vendor_name':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.vendor_name');
        case 'vendor_name_ordinal':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.vendor_name_ordinal');
        case 'stale':
            return i18n.t('hardware.modals.soaibenchHistory.matchBases.stale');
        default:
            return formatUnexpectedSoAIBenchIdentifierLabel(value);
    }
};

const resolveSoAIBenchCapabilityReasonLabel = (reason: string | null): string | null => {
    switch (reason) {
        case 'opencl_compiler_unavailable':
            return i18n.t('hardware.errors.opencl_compiler_unavailable');
        case 'opencl_kernel_execution_unavailable':
            return i18n.t('hardware.errors.opencl_kernel_execution_unavailable');
        case 'opencl_custom_identity_unproved':
            return i18n.t('hardware.errors.opencl_custom_identity_unproved');
        case 'opencl_memory_insufficient':
            return i18n.t('hardware.errors.opencl_memory_insufficient');
        default:
            return null;
    }
};

const resolveSoAIBenchReasonLabel = (reasonMessage: string | null, failureReason: string | null, unsupportedReason: string | null, staleHardware: boolean, guidanceMessage: string | null = null, deadline: SoAIBenchDeadline | null = null): string | null => {
    const rawReason = failureReason || unsupportedReason;
    if (rawReason === 'opencl_child_exited') return i18n.t('hardware.errors.opencl_child_exited');
    if (rawReason === 'opencl_child_invalid_response') return i18n.t('hardware.errors.opencl_child_invalid_response');
    if (rawReason === 'opencl_child_disconnected') return i18n.t('hardware.errors.opencl_child_disconnected');
    const deadlineReason = resolveDeadlineReason(rawReason, deadline);
    if (deadlineReason !== null) return deadlineReason;
    const capabilityReason = resolveSoAIBenchCapabilityReasonLabel(rawReason);
    if (capabilityReason !== null) {
        return capabilityReason;
    }
    let reason: string | null;
    if (rawReason === 'opencl_numerical_mismatch') {
        reason = i18n.t('hardware.modals.soaibenchHistory.reasons.opencl_numerical_mismatch');
    } else if (reasonMessage) {
        reason = reasonMessage.replace(/(?<![A-Za-z0-9_.-])SoAIBench(?![A-Za-z0-9_])/g, i18n.t('hardware.modals.soaibenchRun.title'));
    } else if (rawReason) {
        reason = formatUnexpectedSoAIBenchIdentifierLabel(rawReason);
    } else {
        reason = staleHardware ? i18n.t('hardware.modals.soaibenchHistory.staleHardware') : null;
    }
    return reason && guidanceMessage ? `${reason} — ${guidanceMessage}` : reason;
};

export { formatUnexpectedSoAIBenchIdentifierLabel, resolveSoAIBenchCapabilityReasonLabel, resolveSoAIBenchMatchBasisLabel, resolveSoAIBenchPhaseLabel, resolveSoAIBenchProfileLabel, resolveSoAIBenchReasonLabel, resolveSoAIBenchStatusLabel };
export type { SoAIBenchDeadline };
