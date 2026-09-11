/* SoAI - Chat feature loading activity collapse policy [frontend/assets/ts/features/chat/message/messageview/loadingActivityCollapsePolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const COLLAPSED_LOADING_CONTENT_DATA_ATTR = 'data-collapsed-loading-content';
const COLLAPSED_LOADING_CONTENT_DATA_VALUE = 'true';

const COLLAPSED_LOADING_CONTENT_WRAPPER_ATTRIBUTE = `${COLLAPSED_LOADING_CONTENT_DATA_ATTR}="${COLLAPSED_LOADING_CONTENT_DATA_VALUE}"`;
const COLLAPSED_LOADING_CONTENT_SELECTOR = `[${COLLAPSED_LOADING_CONTENT_DATA_ATTR}="${COLLAPSED_LOADING_CONTENT_DATA_VALUE}"]`;

const COLLAPSED_LOADING_SUMMARY_SELECTOR = '.inline-activity.inline-activity-type-loading[data-loading-stack="true"]';

const resolveDirectCollapsedLoadingElement = (root: Element, selector: string, failureMessage: string): HTMLElement | null => {
    let resolved: HTMLElement | null = null;
    for (const child of Array.from(root.children)) {
        if (!(child instanceof HTMLElement) || !child.matches(selector)) {
            continue;
        }
        if (resolved !== null) {
            throw new Error(failureMessage);
        }
        resolved = child;
    }
    return resolved;
};

const resolveDirectCollapsedLoadingContent = (root: Element): HTMLElement | null => {
    return resolveDirectCollapsedLoadingElement(root, COLLAPSED_LOADING_CONTENT_SELECTOR, 'Assistant body contains multiple collapsed loading content containers');
};

const resolveDirectCollapsedLoadingSummary = (root: Element): HTMLElement | null => {
    return resolveDirectCollapsedLoadingElement(root, COLLAPSED_LOADING_SUMMARY_SELECTOR, 'Assistant body contains multiple collapsed loading summaries');
};

const isRetainedLoadingContentElement = (element: HTMLElement): boolean => {
    return !element.classList.contains('inline-action-update') && !element.classList.contains('inline-activity') && !element.classList.contains('assistant-activity-widgets') && !element.classList.contains('message-error');
};

const shouldCollapseLoadingActivities = (inputArguments: { isShowActivitiesEnabled: boolean; collapsedOverride: boolean | null }): boolean => {
    if (!inputArguments.isShowActivitiesEnabled) {
        return true;
    }
    return inputArguments.collapsedOverride === true;
};

export { isRetainedLoadingContentElement, resolveDirectCollapsedLoadingContent, resolveDirectCollapsedLoadingSummary, COLLAPSED_LOADING_CONTENT_DATA_ATTR, COLLAPSED_LOADING_CONTENT_DATA_VALUE, COLLAPSED_LOADING_CONTENT_SELECTOR, COLLAPSED_LOADING_CONTENT_WRAPPER_ATTRIBUTE, COLLAPSED_LOADING_SUMMARY_SELECTOR, shouldCollapseLoadingActivities };
