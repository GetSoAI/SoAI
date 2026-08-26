/* SoAI - Settings feature token list view [frontend/assets/ts/features/settings/tokenflow/tokenListView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SettingsTokenStatus, SettingsTokenStatusLabels } from '@features/settings/tokenflow/types.ts';
import { serverEpochMs } from '@core/time/clock.ts';

const resolveSettingsTokenStatus = (revoked: boolean, expiresAtMs: number | null | undefined, nowMs: number = serverEpochMs()): SettingsTokenStatus => {
    if (revoked) {
        return 'revoked';
    }
    if (expiresAtMs !== null && expiresAtMs !== undefined && expiresAtMs <= nowMs) {
        return 'expired';
    }
    return 'active';
};

const resolveSettingsTokenItemStateClass = (status: SettingsTokenStatus): string => {
    switch (status) {
        case 'active':
            return '';
        case 'revoked':
            return 'settings-record-item--danger';
        case 'expired':
            return 'settings-record-item--warning';
        default: {
            const exhaustive: never = status;
            throw new Error(`Unhandled settings token status: ${exhaustive}`);
        }
    }
};

const resolveSettingsTokenBadgeClass = (status: SettingsTokenStatus): string => {
    switch (status) {
        case 'active':
            return 'active';
        case 'revoked':
            return 'danger';
        case 'expired':
            return 'warning';
        default: {
            const exhaustive: never = status;
            throw new Error(`Unhandled settings token badge status: ${exhaustive}`);
        }
    }
};

const resolveSettingsTokenStatusLabel = (status: SettingsTokenStatus, labels: SettingsTokenStatusLabels): string => {
    return labels[status];
};

export { resolveSettingsTokenBadgeClass, resolveSettingsTokenItemStateClass, resolveSettingsTokenStatus, resolveSettingsTokenStatusLabel };
