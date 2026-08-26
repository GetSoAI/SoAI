/* SoAI - Dashboard page controllers events [frontend/assets/ts/pages/dashboard/controllers/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { DASHBOARD_ACTION_CLOCK_MODE_CYCLE, DASHBOARD_ACTION_IMAGE_DELETE, DASHBOARD_ACTION_IMAGE_TOGGLE_FIT, DASHBOARD_ACTION_IMAGE_UPLOAD, DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE, DASHBOARD_ACTION_LOGS_SIZE_DECREASE, DASHBOARD_ACTION_LOGS_SIZE_INCREASE, DASHBOARD_ACTION_MEMO_CANCEL, DASHBOARD_ACTION_MEMO_EDIT, DASHBOARD_ACTION_MEMO_SAVE, DASHBOARD_ACTION_QUICK_ACTION_NAVIGATE, DASHBOARD_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE, type DashboardActionId } from '@pages/dashboard/actions.ts';

const QUICK_ACTION_PAGE_ATTRIBUTE = 'quick-action-page';

type DashboardActionHandler = (actionElement: HTMLElement) => void;

interface DashboardActionHandlers {
    onLogsAction: (actionId: DashboardActionId, target: HTMLElement) => void;
    onImageUploadOpen: () => void;
    onImageDelete: () => void;
    onImageToggleFit: () => void;
    onMemoCancel: () => void;
    onMemoEdit: () => void;
    onMemoSave: () => void;
    onClockModeCycle: () => void;
    onRequestDistributionSourceToggle: () => void;
    onQuickActionNavigate: (pageId: string) => void;
}

const createDashboardActionHandlers = (dependencies: DashboardActionHandlers): Readonly<Record<DashboardActionId, DashboardActionHandler>> => {
    return {
        [DASHBOARD_ACTION_LOGS_SIZE_DECREASE]: (actionElement: HTMLElement): void => {
            dependencies.onLogsAction(DASHBOARD_ACTION_LOGS_SIZE_DECREASE, actionElement);
        },
        [DASHBOARD_ACTION_LOGS_SIZE_INCREASE]: (actionElement: HTMLElement): void => {
            dependencies.onLogsAction(DASHBOARD_ACTION_LOGS_SIZE_INCREASE, actionElement);
        },
        [DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE]: (actionElement: HTMLElement): void => {
            dependencies.onLogsAction(DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE, actionElement);
        },
        [DASHBOARD_ACTION_IMAGE_UPLOAD]: (): void => {
            dependencies.onImageUploadOpen();
        },
        [DASHBOARD_ACTION_IMAGE_DELETE]: (): void => {
            dependencies.onImageDelete();
        },
        [DASHBOARD_ACTION_IMAGE_TOGGLE_FIT]: (): void => {
            dependencies.onImageToggleFit();
        },
        [DASHBOARD_ACTION_MEMO_CANCEL]: (): void => {
            dependencies.onMemoCancel();
        },
        [DASHBOARD_ACTION_MEMO_EDIT]: (): void => {
            dependencies.onMemoEdit();
        },
        [DASHBOARD_ACTION_MEMO_SAVE]: (): void => {
            dependencies.onMemoSave();
        },
        [DASHBOARD_ACTION_CLOCK_MODE_CYCLE]: (): void => {
            dependencies.onClockModeCycle();
        },
        [DASHBOARD_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE]: (): void => {
            dependencies.onRequestDistributionSourceToggle();
        },
        [DASHBOARD_ACTION_QUICK_ACTION_NAVIGATE]: (actionElement: HTMLElement): void => {
            dependencies.onQuickActionNavigate(requireTrimmedDataAttribute(actionElement, QUICK_ACTION_PAGE_ATTRIBUTE, 'Dashboard quick action'));
        }
    };
};

export { createDashboardActionHandlers };
