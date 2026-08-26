/* SoAI - Shared UI notifications constants [frontend/assets/ts/core/ui/notifications/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

const NOTIFICATION_ICON_MAP: Readonly<Record<NotificationType, IconName>> = Object.freeze({
    success: 'success-modal',
    error: 'error-modal',
    warning: 'warning-modal',
    danger: 'danger-modal',
    info: 'info-modal',
    copy: 'copy',
    refresh: 'refresh',
    download: 'download'
});

const USER_NOTIFICATION_DURATIONS: Readonly<Record<NotificationType, number>> = Object.freeze({
    error: 5000,
    danger: 5000,
    warning: 4000,
    success: 3000,
    info: 3000,
    copy: 3000,
    refresh: 3000,
    download: 3000
});

const NOTIFICATION_DISMISS_FADE_MS = 200;

export { NOTIFICATION_DISMISS_FADE_MS, NOTIFICATION_ICON_MAP, USER_NOTIFICATION_DURATIONS };
