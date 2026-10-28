/* SoAI - Software update outcome and server version recovery [frontend/assets/ts/app/bootstrap/stages/applifecycle/softwareUpdateRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APPLICATION_UPDATE_HISTORY_KEY, saveCompletedUpdate, type UpdateHistoryStorage } from '@core/updates/updateHistory.ts';
import { readBackendUpdateOutcome } from '@app/bootstrap/stages/applifecycle/backendUpdateOutcome.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { RestartOverlayApi } from '@app/bootstrap/stages/applifecycle/types.ts';
import type { SoftwareUpdateDiagnostics, SoftwareUpdateDiagnosticsClassification, SoftwareUpdateNotice } from '@core/api/contracts/softwareContracts.ts';
import type { SystemHealthResponse } from '@core/api/contracts/systemContracts.ts';
import type { SoftwareEndpoints } from '@core/api/endpoints/software.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { AuthManager } from '@core/auth/public.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { getLocation } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';

const SERVER_VERSION_PROBE_TIMEOUT_MS = 15000;

interface SoftwareUpdateRecoveryDependencies {
    readonly frontendVersion: string;
    storage: UpdateHistoryStorage;
    router: Pick<Router, 'navigate' | 'getCurrentRoute'>;
    auth: Pick<AuthManager, 'onLogout'>;
    api: {
        software: Pick<SoftwareEndpoints, 'getUpdateNotice' | 'acknowledgeUpdateNotice' | 'getUpdateDiagnostics'>;
        system: { health: (options?: RequestOptions) => Promise<SystemHealthResponse> };
    };
    restartOverlay: Pick<RestartOverlayApi, 'currentType'>;
}

interface ServerVersionMonitor {
    verify: () => Promise<void>;
}

const outcomeSequences = new WeakMap<WeakKey, SequenceToken>();

const readOutcomeSequence = (owner: WeakKey): SequenceToken => {
    const existing = outcomeSequences.get(owner);
    if (existing !== undefined) return existing;
    const created = new SequenceToken();
    outcomeSequences.set(owner, created);
    return created;
};

const describeDiagnosticsClassification = (classification: SoftwareUpdateDiagnosticsClassification): string => {
    switch (classification) {
        case 'retained_copy_mismatch':
            return i18n.t('updates.outcome.diagnosticsRetainedCopyMismatch');
        case 'installed_original_changed':
            return i18n.t('updates.outcome.diagnosticsInstalledOriginalChanged');
        case 'source_unverifiable':
            return i18n.t('updates.outcome.diagnosticsSourceUnverifiable');
        case 'snapshot_operation_failed':
            return i18n.t('updates.outcome.diagnosticsSnapshotOperationFailed');
        case 'interrupted_preparation':
            return i18n.t('updates.outcome.diagnosticsInterruptedPreparation');
    }
};

const readFailureDiagnostics = async ({ api }: Pick<SoftwareUpdateRecoveryDependencies, 'api'>, taskId: string, signal: AbortSignal): Promise<SoftwareUpdateDiagnostics | null> => {
    try {
        return await api.software.getUpdateDiagnostics(taskId, { signal });
    } catch (error) {
        if (isAbortError(error)) return null;
        errorHandler.debug('AppLifecycle', 'Software update diagnostics are not available to this session', ensureError(error));
        return null;
    }
};

const describeFailure = (notice: SoftwareUpdateNotice, diagnostics: SoftwareUpdateDiagnostics | null): string => {
    const failure = i18n.t('updates.outcome.failureMessage', { version: notice.toVersion, previousVersion: notice.fromVersion });
    if (diagnostics === null || diagnostics.status !== 'available' || diagnostics.location === null || diagnostics.classification === null || diagnostics.reference === null) return failure;
    const details = i18n.t('updates.outcome.diagnosticsMessage', { summary: describeDiagnosticsClassification(diagnostics.classification), location: diagnostics.location, reference: diagnostics.reference });
    return `${failure}\n\n${details}`;
};

const presentSoftwareUpdateOutcome = async ({ api, auth, router, storage }: Pick<SoftwareUpdateRecoveryDependencies, 'api' | 'auth' | 'router' | 'storage'>): Promise<void> => {
    const sequence = readOutcomeSequence(api.software);
    const presentation = sequence.next();
    const controller = new AbortController();
    const unsubscribe = auth.onLogout(() => controller.abort());
    try {
        const notice = await api.software.getUpdateNotice({ signal: controller.signal });
        if (notice === null || controller.signal.aborted || !sequence.isActive(presentation)) return;
        const completed = notice.status === 'completed';
        let historySaved = true;
        if (completed) {
            try {
                await saveCompletedUpdate(storage, APPLICATION_UPDATE_HISTORY_KEY, notice.finishedAtMs);
            } catch (error) {
                historySaved = false;
                errorHandler.warn('AppLifecycle', 'Completed software update history could not be saved', ensureError(error));
            }
        }
        const diagnostics = completed ? null : await readFailureDiagnostics({ api }, notice.taskId, controller.signal);
        if (controller.signal.aborted || !sequence.isActive(presentation)) return;
        const backendOutcome: Awaited<ReturnType<typeof readBackendUpdateOutcome>> = completed ? await readBackendUpdateOutcome(router, controller.signal) : {};
        if (controller.signal.aborted || !sequence.isActive(presentation)) return;
        const { waitForReview, ...noticeOptions } = backendOutcome;
        const acknowledged = await requireDialogsService().showNotice({
            ...noticeOptions,
            signal: controller.signal,
            title: completed ? i18n.t('updates.outcome.successTitle') : i18n.t('updates.outcome.failureTitle'),
            message: completed ? `${i18n.t('updates.outcome.successMessage', { version: notice.toVersion })}${historySaved ? '' : `\n\n${i18n.t('updates.history.unavailable')}`}` : describeFailure(notice, diagnostics),
            variant: completed ? 'success' : 'danger'
        });
        const reviewed = !acknowledged && waitForReview ? await waitForReview() : false;
        if ((!acknowledged && !reviewed) || controller.signal.aborted || !sequence.isActive(presentation)) return;
        if (!historySaved) return;
        await api.software.acknowledgeUpdateNotice(notice.taskId, { signal: controller.signal });
    } catch (error) {
        if (isAbortError(error)) return;
        throw ensureError(error);
    } finally {
        unsubscribe();
    }
};

const createServerVersionMonitor = ({ api, restartOverlay, frontendVersion }: SoftwareUpdateRecoveryDependencies): ServerVersionMonitor => {
    let reloadPromptOpen = false;
    const probes = new SequenceToken();
    const verify = async (): Promise<void> => {
        const probe = probes.next();
        const { version } = await api.system.health({ timeoutMs: SERVER_VERSION_PROBE_TIMEOUT_MS });
        if (!probes.isActive(probe) || version === frontendVersion || reloadPromptOpen || restartOverlay.currentType === 'update-soai') return;
        reloadPromptOpen = true;
        try {
            const reload = await requireDialogsService().showConfirmation({
                title: i18n.t('updates.outcome.reloadTitle'),
                message: i18n.t('updates.outcome.reloadMessage', { version }),
                confirmText: i18n.t('common.connection.reloadPage'),
                cancelText: i18n.t('updates.outcome.later'),
                variant: 'info',
                confirmVariant: 'ui-variant-accent'
            });
            if (reload) getLocation().reload();
        } finally {
            reloadPromptOpen = false;
        }
    };
    return { verify };
};

export { createServerVersionMonitor, presentSoftwareUpdateOutcome };
export type { ServerVersionMonitor, SoftwareUpdateRecoveryDependencies };
