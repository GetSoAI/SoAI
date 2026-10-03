/* SoAI - Software update outcome and server version recovery [frontend/assets/ts/app/bootstrap/stages/applifecycle/softwareUpdateRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RestartOverlayApi } from '@app/bootstrap/stages/applifecycle/types.ts';
import type { SystemHealthResponse } from '@core/api/contracts/systemContracts.ts';
import type { SoftwareEndpoints } from '@core/api/endpoints/software.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { getLocation } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';

const SERVER_VERSION_PROBE_TIMEOUT_MS = 15000;

interface SoftwareUpdateRecoveryDependencies {
    readonly frontendVersion: string;
    api: {
        software: Pick<SoftwareEndpoints, 'getUpdateNotice' | 'acknowledgeUpdateNotice'>;
        system: { health: (options?: RequestOptions) => Promise<SystemHealthResponse> };
    };
    restartOverlay: Pick<RestartOverlayApi, 'currentType'>;
}

interface ServerVersionMonitor {
    verify: () => Promise<void>;
}

const presentSoftwareUpdateOutcome = async ({ api }: Pick<SoftwareUpdateRecoveryDependencies, 'api'>): Promise<void> => {
    const notice = await api.software.getUpdateNotice();
    if (notice === null) return;
    const completed = notice.status === 'completed';
    await requireDialogsService().showNotice({
        title: completed ? i18n.t('updates.outcome.successTitle') : i18n.t('updates.outcome.failureTitle'),
        message: completed ? i18n.t('updates.outcome.successMessage', { version: notice.toVersion }) : i18n.t('updates.outcome.failureMessage', { version: notice.toVersion, previousVersion: notice.fromVersion }),
        variant: completed ? 'success' : 'danger'
    });
    await api.software.acknowledgeUpdateNotice(notice.taskId);
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
