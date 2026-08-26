/* SoAI - Hardware page processes effects [frontend/assets/ts/pages/hardware/widgets/processes/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractUserFacingErrorMessage } from '@core/errors/coerce.ts';
import { APIError } from '@core/apiError.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ProcessKillRequestOptions, ProcessKillResolution } from '@pages/hardware/widgets/processes/types.ts';

type ResolveKillProcessErrorParameters = {
    error: Error;
    pid: number | string;
    processName: string;
    attemptedSudo: boolean;
    supportsElevatedKill: boolean;
};

const resolveKillProcessError = ({ error, pid, processName, attemptedSudo, supportsElevatedKill }: ResolveKillProcessErrorParameters): ProcessKillResolution => {
    const genericFailureMessage = i18n.t('hardware.processes.notifications.killFailedGeneric');

    const status = error instanceof APIError ? error.status : 0;
    const rawMessage = extractUserFacingErrorMessage(error) ?? '';
    const normalizedMessage = rawMessage.toLowerCase();

    if (status === 0 && !normalizedMessage) return { message: i18n.t('hardware.processes.notifications.killFailedNetwork'), type: 'error' };

    if (status === 404 || /no such process|not found/.test(normalizedMessage)) {
        return { message: i18n.t('hardware.processes.notifications.processMissing', { name: processName, pid }), type: 'info' };
    }

    if (!attemptedSudo && (status === 403 || /not permitted|permission denied|access denied/.test(normalizedMessage))) {
        return {
            message: supportsElevatedKill ? i18n.t('hardware.processes.notifications.permissionDenied', { name: processName, pid }) : i18n.t('hardware.processes.notifications.permissionDeniedNoEscalation', { name: processName, pid }),
            type: 'warning',
            retryElevated: supportsElevatedKill
        };
    }

    if (status === 400 && /invalid signal|invalid pid/.test(normalizedMessage)) {
        return { message: genericFailureMessage, type: 'error' };
    }

    return { message: rawMessage ? rawMessage : genericFailureMessage, type: 'error' };
};

type ExecuteKillOptions = {
    signal?: number;
    useSudo?: boolean;
};

const normalizeKillOptions = ({ signal = 15, useSudo = false }: ExecuteKillOptions = {}): ProcessKillRequestOptions => {
    return {
        signal,
        useSudo
    };
};

export { normalizeKillOptions, resolveKillProcessError };
