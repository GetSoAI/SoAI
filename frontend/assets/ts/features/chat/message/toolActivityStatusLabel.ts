/* SoAI - Chat feature tool activity status label [frontend/assets/ts/features/chat/message/toolActivityStatusLabel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

const resolveToolActivityStatusLabelKey = (statusKey: string): string => {
    if (statusKey === 'cancelled') {
        return 'completed';
    }
    return statusKey;
};

const resolveToolActivityStatusLabel = (statusKey: string): string => {
    const resolvedKey = resolveToolActivityStatusLabelKey(statusKey);
    if (resolvedKey === 'running') {
        return i18n.t('chat.toolActivity.status.running');
    }
    if (resolvedKey === 'completed') {
        return i18n.t('chat.toolActivity.status.completed');
    }
    if (resolvedKey === 'error') {
        return i18n.t('chat.toolActivity.status.error');
    }
    return i18n.t('chat.toolActivity.status.pending');
};

export { resolveToolActivityStatusLabel, resolveToolActivityStatusLabelKey };
