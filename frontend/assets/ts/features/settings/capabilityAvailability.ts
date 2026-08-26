/* SoAI - Settings feature capability availability [frontend/assets/ts/features/settings/capabilityAvailability.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatRelativeTime } from '@core/primitives/dateTime.ts';
import { securityApi } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { SettingsCapabilityAvailability } from '@core/settings/contracts.ts';

interface SettledSettingsCapability<Result> {
    succeeded: boolean;
    value: Result | null;
    error: Error | null;
}

type SettingsCapabilityRequest<Result> = Promise<Result> | (() => Promise<Result>);

const createSettingsCapabilityAvailability = (): SettingsCapabilityAvailability => ({
    status: 'pending',
    updatedAtMs: null
});

const markSettingsCapabilityReady = (updatedAtMs: number = serverEpochMs()): SettingsCapabilityAvailability => ({
    status: 'ready',
    updatedAtMs
});

const markSettingsCapabilityFailed = (previous: SettingsCapabilityAvailability, hasPartialSuccess: boolean = false, updatedAtMs?: number): SettingsCapabilityAvailability => {
    if (hasPartialSuccess) {
        return {
            status: 'partial',
            updatedAtMs: updatedAtMs ?? serverEpochMs()
        };
    }
    if (previous.updatedAtMs !== null) {
        return {
            status: 'stale',
            updatedAtMs: previous.updatedAtMs
        };
    }
    return {
        status: 'unavailable',
        updatedAtMs: null
    };
};

const settleSettingsCapability = async <Result>(request: SettingsCapabilityRequest<Result>): Promise<SettledSettingsCapability<Result>> => {
    const requestTask = typeof request === 'function' ? Promise.resolve().then(request) : request;
    return await requestTask.then(
        (value): SettledSettingsCapability<Result> => ({
            succeeded: true,
            value,
            error: null
        }),
        (error): SettledSettingsCapability<Result> => ({
            succeeded: false,
            value: null,
            error: ensureError(error)
        })
    );
};

const resolveSettingsCapabilityMessage = (availability: SettingsCapabilityAvailability): string | null => {
    if (availability.status === 'pending' || availability.status === 'ready') {
        return null;
    }
    let message = i18n.t('settings.availability.unavailable');
    if (availability.status === 'partial') {
        message = i18n.t('settings.availability.partial');
    } else if (availability.status === 'stale' && availability.updatedAtMs !== null) {
        message = i18n.t('settings.availability.stale', { age: formatRelativeTime(availability.updatedAtMs, serverEpochMs()) });
    }
    return message;
};

const renderSettingsCapabilityNotice = (availability: SettingsCapabilityAvailability): string => {
    const message = resolveSettingsCapabilityMessage(availability);
    return message === null ? '' : `<div class="settings-card-surface settings-capability-notice" role="status">${securityApi.escapeHtml(message)}</div>`;
};

export { createSettingsCapabilityAvailability, markSettingsCapabilityFailed, markSettingsCapabilityReady, renderSettingsCapabilityNotice, resolveSettingsCapabilityMessage, settleSettingsCapability };
export type { SettingsCapabilityAvailability, SettledSettingsCapability };
