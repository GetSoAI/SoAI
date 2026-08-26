/* SoAI - Tasks feature status progress [frontend/assets/ts/features/tasks/taskmanagerstore/statusProgress.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { ACTIVE_STATUSES, BLOCKING_PLUGIN_STATUSES, PERSISTENT_STATUS, PROGRESS_STATUSES } from '@features/tasks/taskmanagerstore/constants.ts';

const normalizeTaskStatus = (status: string | null | undefined, normalizeStatus: (status: string | null | undefined) => string): string => {
    return normalizeStatus(status).toUpperCase();
};

const isBlockingPluginStatus = (status: string | null | undefined, normalizeStatus: (status: string | null | undefined) => string): boolean => BLOCKING_PLUGIN_STATUSES.has(normalizeTaskStatus(status, normalizeStatus));

const isActiveStatus = (status: string | null | undefined, normalizeStatus: (status: string | null | undefined) => string): boolean => ACTIVE_STATUSES.has(isString(status) ? normalizeStatus(status) : '');

const isPersistentStatus = (status: string | null | undefined, normalizeStatus: (status: string | null | undefined) => string): boolean => normalizeStatus(status) === PERSISTENT_STATUS;

const shouldShowProgress = (status: string | null | undefined, normalizeStatus: (status: string | null | undefined) => string): boolean => {
    const normalizedStatus = normalizeStatus(status || '');
    return PROGRESS_STATUSES.has(normalizedStatus);
};

export { isActiveStatus, isBlockingPluginStatus, isPersistentStatus, normalizeTaskStatus, shouldShowProgress };
