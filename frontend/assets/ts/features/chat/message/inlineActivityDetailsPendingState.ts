/* SoAI - Chat feature inline activity details pending state [frontend/assets/ts/features/chat/message/inlineActivityDetailsPendingState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { getTooltipText, setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { buildInlineActivityDetailsDomKey } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, resolveDirectInlineActivityDetailsRoot } from '@features/chat/message/inlineActivityDetailsIdentity.ts';

const INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE = 'data-details-open-pending';
const INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE = 'data-details-loading';
const INLINE_ACTIVITY_DETAILS_LOADING_SPINNER_CLASS = 'inline-activity-details-loading-spinner';
const INLINE_ACTIVITY_CLOSE_BUTTON_SELECTOR = ':scope > .inline-activity-header > .inline-activity-close-button';

interface PendingInlineActivityDetailsState {
    activity: HTMLElement | null;
    loadingFrame: number | null;
    closeButtonAriaLabel: string | null;
    closeButtonTooltip: string | null;
    closeButtonAttributesCaptured: boolean;
}

const pendingStateByActivityKey = new Map<string, PendingInlineActivityDetailsState>();

const resolveCloseButton = (activity: HTMLElement): HTMLButtonElement | null => {
    const button = dom.resolve(INLINE_ACTIVITY_CLOSE_BUTTON_SELECTOR, activity);
    return button instanceof HTMLButtonElement ? button : null;
};

const closeButtonHasLoadingSpinner = (button: HTMLButtonElement): boolean => {
    return dom.resolve(`:scope > .${INLINE_ACTIVITY_DETAILS_LOADING_SPINNER_CLASS}.loading-spinner`, button) !== null;
};

const createPendingState = (): PendingInlineActivityDetailsState => ({
    activity: null,
    loadingFrame: null,
    closeButtonAriaLabel: null,
    closeButtonTooltip: null,
    closeButtonAttributesCaptured: false
});

const resolvePendingStateKey = (activity: HTMLElement): string | null => buildInlineActivityDetailsDomKey(activity);

const resolvePendingState = (activity: HTMLElement): PendingInlineActivityDetailsState => {
    const key = resolvePendingStateKey(activity);
    if (key === null) {
        return createPendingState();
    }
    const existing = pendingStateByActivityKey.get(key);
    if (existing) {
        return existing;
    }
    const created = createPendingState();
    pendingStateByActivityKey.set(key, created);
    return created;
};

const clearLoadingFrame = (activity: HTMLElement, state: PendingInlineActivityDetailsState): void => {
    if (state.loadingFrame === null) {
        return;
    }
    activity.ownerDocument.defaultView?.cancelAnimationFrame(state.loadingFrame);
    state.loadingFrame = null;
};

const captureCloseButtonState = (button: HTMLButtonElement, state: PendingInlineActivityDetailsState): void => {
    state.closeButtonAriaLabel = button.getAttribute('aria-label');
    state.closeButtonTooltip = getTooltipText(button);
    state.closeButtonAttributesCaptured = true;
};

const restoreCloseButton = (activity: HTMLElement, state: PendingInlineActivityDetailsState): void => {
    const button = resolveCloseButton(activity);
    if (!(button instanceof HTMLButtonElement)) {
        state.closeButtonAriaLabel = null;
        state.closeButtonTooltip = null;
        state.closeButtonAttributesCaptured = false;
        return;
    }
    dom.resolve(`:scope > .${INLINE_ACTIVITY_DETAILS_LOADING_SPINNER_CLASS}.loading-spinner`, button)?.remove();
    if (!state.closeButtonAttributesCaptured) {
        const closeLabel = i18n.t('common.close');
        button.setAttribute('aria-label', closeLabel);
        setTooltipText(button, closeLabel);
        return;
    }
    if (state.closeButtonAriaLabel === null) {
        button.removeAttribute('aria-label');
    } else {
        button.setAttribute('aria-label', state.closeButtonAriaLabel);
    }
    if (state.closeButtonTooltip === null) {
        setTooltipText(button, '');
    } else {
        setTooltipText(button, state.closeButtonTooltip);
    }
    state.closeButtonAriaLabel = null;
    state.closeButtonTooltip = null;
    state.closeButtonAttributesCaptured = false;
};

const renderLoadingSpinner = (button: HTMLButtonElement): void => {
    if (closeButtonHasLoadingSpinner(button)) {
        return;
    }
    const documentRef = button.ownerDocument;
    const spinner = documentRef.createElement('span');
    spinner.className = `loading-spinner ${INLINE_ACTIVITY_DETAILS_LOADING_SPINNER_CLASS}`;
    spinner.setAttribute('aria-hidden', 'true');
    button.appendChild(spinner);
};

const showInlineActivityDetailsLoading = (activity: HTMLElement): void => {
    if (activity.getAttribute(INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE) !== 'true') {
        return;
    }
    const state = resolvePendingState(activity);
    const button = resolveCloseButton(activity);
    if (!(button instanceof HTMLButtonElement)) {
        return;
    }
    if (!closeButtonHasLoadingSpinner(button)) {
        captureCloseButtonState(button, state);
    }
    const loadingLabel = i18n.t('common.loading');
    button.setAttribute('aria-label', loadingLabel);
    setTooltipText(button, loadingLabel);
    activity.setAttribute(INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE, 'true');
    renderLoadingSpinner(button);
};

const beginInlineActivityDetailsPendingState = (activity: HTMLElement): void => {
    const key = resolvePendingStateKey(activity);
    const state = resolvePendingState(activity);
    clearLoadingFrame(activity, state);
    state.activity = activity;
    if (activity.getAttribute('data-collapsed') === 'true') {
        activity.setAttribute('data-collapsing', 'true');
    }
    activity.setAttribute(INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE, 'true');
    activity.removeAttribute(INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE);
    restoreCloseButton(activity, state);
    const view = activity.ownerDocument.defaultView;
    if (view === null || typeof view.requestAnimationFrame !== 'function') {
        showInlineActivityDetailsLoading(activity);
        return;
    }
    state.loadingFrame = view.requestAnimationFrame(() => {
        state.loadingFrame = null;
        if (!activity.isConnected) {
            if (key !== null) {
                pendingStateByActivityKey.delete(key);
            }
            return;
        }
        showInlineActivityDetailsLoading(activity);
    });
};

const ensureInlineActivityDetailsPendingState = (activity: HTMLElement): void => {
    const key = resolvePendingStateKey(activity);
    const state = key === null ? null : (pendingStateByActivityKey.get(key) ?? null);
    const isPending = activity.getAttribute(INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE) === 'true';
    const isLoading = activity.getAttribute(INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE) === 'true';
    if (state !== null && state.activity === activity && (state.loadingFrame !== null || (isPending && isLoading))) {
        return;
    }
    if (isPending && isLoading) {
        const adoptedState = resolvePendingState(activity);
        clearLoadingFrame(activity, adoptedState);
        adoptedState.activity = activity;
        showInlineActivityDetailsLoading(activity);
        return;
    }
    beginInlineActivityDetailsPendingState(activity);
};

const clearInlineActivityDetailsPendingState = (activity: HTMLElement): void => {
    const key = resolvePendingStateKey(activity);
    const state = key === null ? createPendingState() : (pendingStateByActivityKey.get(key) ?? createPendingState());
    activity.removeAttribute(INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE);
    activity.removeAttribute(INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE);
    clearLoadingFrame(activity, state);
    restoreCloseButton(activity, state);
    state.activity = null;
    if (key !== null) {
        pendingStateByActivityKey.delete(key);
    }
};

const stabilizeInlineActivityDetailsOpeningLayout = (activity: HTMLElement): void => {
    if (activity.getAttribute('data-collapsed') !== 'true') {
        return;
    }
    const detailsRoot = resolveDirectInlineActivityDetailsRoot(activity);
    if (!(detailsRoot instanceof HTMLElement)) {
        return;
    }
    activity.setAttribute('data-collapsing', 'true');
    void detailsRoot.offsetHeight;
};

const completeInlineActivityDetailsOpenState = (activity: HTMLElement): void => {
    activity.removeAttribute(INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE);
    stabilizeInlineActivityDetailsOpeningLayout(activity);
    activity.setAttribute('data-collapsed', 'false');
    activity.removeAttribute('data-collapsing');
    clearInlineActivityDetailsPendingState(activity);
};

const resetInlineActivityDetailsClosedState = (activity: HTMLElement): void => {
    activity.removeAttribute(INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE);
    activity.removeAttribute('data-collapsing');
    activity.setAttribute('data-collapsed', 'true');
    clearInlineActivityDetailsPendingState(activity);
};

const isInlineActivityDetailsPending = (activity: HTMLElement): boolean => activity.getAttribute(INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE) === 'true';

const reapplyInlineActivityDetailsPendingChrome = (activity: HTMLElement): void => {
    const key = resolvePendingStateKey(activity);
    const state = key === null ? null : (pendingStateByActivityKey.get(key) ?? null);
    if (state === null && activity.getAttribute(INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE) !== 'true') {
        return;
    }
    if (activity.getAttribute(INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE) === 'true') {
        showInlineActivityDetailsLoading(activity);
    }
};

export { INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE, INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE, beginInlineActivityDetailsPendingState, clearInlineActivityDetailsPendingState, completeInlineActivityDetailsOpenState, ensureInlineActivityDetailsPendingState, isInlineActivityDetailsPending, reapplyInlineActivityDetailsPendingChrome, resetInlineActivityDetailsClosedState };
