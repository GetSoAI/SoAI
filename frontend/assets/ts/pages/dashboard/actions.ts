/* SoAI - Dashboard page actions [frontend/assets/ts/pages/dashboard/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const DASHBOARD_ACTION_LOGS_SIZE_DECREASE = 'dashboard:logs:size-decrease';
export const DASHBOARD_ACTION_LOGS_SIZE_INCREASE = 'dashboard:logs:size-increase';
export const DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE = 'dashboard:logs:autoscroll';
export const DASHBOARD_ACTION_IMAGE_UPLOAD = 'dashboard:image:upload';
export const DASHBOARD_ACTION_IMAGE_DELETE = 'dashboard:image:delete';
export const DASHBOARD_ACTION_IMAGE_TOGGLE_FIT = 'dashboard:image:toggle-fit';
export const DASHBOARD_ACTION_MEMO_EDIT = 'dashboard:memo:edit';
export const DASHBOARD_ACTION_MEMO_SAVE = 'dashboard:memo:save';
export const DASHBOARD_ACTION_MEMO_CANCEL = 'dashboard:memo:cancel';
export const DASHBOARD_ACTION_CLOCK_MODE_CYCLE = 'dashboard:clock:mode-cycle';
export const DASHBOARD_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE = 'dashboard:requests:source-toggle';
export const DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID = 'dashboardRequestDistributionSourceToggle';
export const DASHBOARD_ACTION_QUICK_ACTION_NAVIGATE = 'dashboard:quickActions:navigate';

export type DashboardActionId = typeof DASHBOARD_ACTION_LOGS_SIZE_DECREASE | typeof DASHBOARD_ACTION_LOGS_SIZE_INCREASE | typeof DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE | typeof DASHBOARD_ACTION_IMAGE_UPLOAD | typeof DASHBOARD_ACTION_IMAGE_DELETE | typeof DASHBOARD_ACTION_IMAGE_TOGGLE_FIT | typeof DASHBOARD_ACTION_MEMO_EDIT | typeof DASHBOARD_ACTION_MEMO_SAVE | typeof DASHBOARD_ACTION_MEMO_CANCEL | typeof DASHBOARD_ACTION_CLOCK_MODE_CYCLE | typeof DASHBOARD_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE | typeof DASHBOARD_ACTION_QUICK_ACTION_NAVIGATE;

const { guard: isDashboardActionId } = createActionIdSet(DASHBOARD_ACTION_LOGS_SIZE_DECREASE, DASHBOARD_ACTION_LOGS_SIZE_INCREASE, DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE, DASHBOARD_ACTION_IMAGE_UPLOAD, DASHBOARD_ACTION_IMAGE_DELETE, DASHBOARD_ACTION_IMAGE_TOGGLE_FIT, DASHBOARD_ACTION_MEMO_EDIT, DASHBOARD_ACTION_MEMO_SAVE, DASHBOARD_ACTION_MEMO_CANCEL, DASHBOARD_ACTION_CLOCK_MODE_CYCLE, DASHBOARD_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE, DASHBOARD_ACTION_QUICK_ACTION_NAVIGATE);

export { isDashboardActionId };
