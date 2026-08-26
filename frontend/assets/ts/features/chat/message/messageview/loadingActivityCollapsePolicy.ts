/* SoAI - Chat feature loading activity collapse policy [frontend/assets/ts/features/chat/message/messageview/loadingActivityCollapsePolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const COLLAPSED_LOADING_CONTENT_DATA_ATTR = 'data-collapsed-loading-content';
const COLLAPSED_LOADING_CONTENT_DATA_VALUE = 'true';

const COLLAPSED_LOADING_CONTENT_WRAPPER_ATTRIBUTE = `${COLLAPSED_LOADING_CONTENT_DATA_ATTR}="${COLLAPSED_LOADING_CONTENT_DATA_VALUE}"`;
const COLLAPSED_LOADING_CONTENT_SELECTOR = `[${COLLAPSED_LOADING_CONTENT_DATA_ATTR}="${COLLAPSED_LOADING_CONTENT_DATA_VALUE}"]`;

const COLLAPSED_LOADING_SUMMARY_SELECTOR = '.inline-activity.inline-activity-type-loading[data-loading-stack="true"]';

const shouldCollapseLoadingActivities = (inputArguments: { isShowActivitiesEnabled: boolean; collapsedOverride: boolean | null }): boolean => {
    if (!inputArguments.isShowActivitiesEnabled) {
        return true;
    }
    return inputArguments.collapsedOverride === true;
};

export { COLLAPSED_LOADING_CONTENT_DATA_ATTR, COLLAPSED_LOADING_CONTENT_DATA_VALUE, COLLAPSED_LOADING_CONTENT_SELECTOR, COLLAPSED_LOADING_CONTENT_WRAPPER_ATTRIBUTE, COLLAPSED_LOADING_SUMMARY_SELECTOR, shouldCollapseLoadingActivities };
