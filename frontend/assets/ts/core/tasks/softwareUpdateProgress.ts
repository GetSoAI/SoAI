/* SoAI - Shared software update preparation presentation [frontend/assets/ts/core/tasks/softwareUpdateProgress.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeSoftwareUpdatePreparationResponse, type SoftwareUpdatePreparationResponse } from '@core/api/contracts/softwareContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import type { OperationProgressData } from '@core/operationprogress/types.ts';
import { resolveOperationProgressDetails } from '@core/operationprogress/transferDetails.ts';
import { normalizeProgressCompletedTotal } from '@core/primitives/progress.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { formatRelativeTime } from '@core/primitives/dateTime.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const preparationMessage = (phase: NonNullable<SoftwareUpdatePreparationResponse['phase']>): string => {
    switch (phase) {
        case 'preparing':
            return i18n.t('updates.status.updating');
        case 'fetching':
            return i18n.t('updates.status.fetching');
        case 'verifying':
            return i18n.t('updates.progress.verifying');
        case 'downloading':
            return i18n.t('updates.progress.downloading');
        case 'staging':
            return i18n.t('updates.progress.staging');
        case 'handoff':
            return i18n.t('updates.progress.handoff');
        case 'unavailable':
            return i18n.t('updates.progress.unavailable');
    }
};

const softwareUpdatePreparationProgress = (preparation: SoftwareUpdatePreparationResponse): OperationProgressData => {
    const phase = preparation.phase ?? 'preparing';
    const progress = phase === 'downloading' ? normalizeProgressCompletedTotal(preparation.downloadedBytes, preparation.totalBytes) : null;
    const details = resolveOperationProgressDetails({ 'downloaded_bytes': preparation.downloadedBytes, 'total_bytes': preparation.totalBytes });
    const retainedAge = phase === 'unavailable' && preparation.updatedAtMs !== null ? formatRelativeTime(preparation.updatedAtMs, Date.now()) : '';
    return {
        message: preparationMessage(phase),
        details: [details, retainedAge].filter(Boolean).join(' · '),
        ...(progress !== null ? { progress } : {}),
        state: 'pending',
        indeterminate: progress === null,
        cancelable: false
    };
};

const softwareUpdateTaskProgress = (taskId: string, details: string): JsonObject => {
    const preparation = details.startsWith('{') ? decodeSoftwareUpdatePreparationResponse(parseRequiredJsonText(details)) : null;
    if (preparation?.taskId && preparation.taskId !== taskId) throw new Error('Software update progress identity mismatch');
    const data = softwareUpdatePreparationProgress(preparation ?? { active: true, taskId, phase: 'preparing', downloadedBytes: null, totalBytes: null, updatedAtMs: null });
    return { indeterminate: data.indeterminate === true, message: data.message ?? '', details: data.details ?? '', ...(data.progress !== undefined ? { progress: data.progress } : {}) };
};

export { preparationMessage, softwareUpdatePreparationProgress, softwareUpdateTaskProgress };
