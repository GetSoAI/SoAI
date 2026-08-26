/* SoAI - Streaming spinner status reconcile signature policy [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusReconcileSignature.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { hasSettledActionButtons, hasVisibleSpinnerActivity } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';
import { STREAM_SPINNER_HAS_LOADING_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_LOADING_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_WAIT_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';

const resolveSpinnerReconcileSignature = (inputArguments: { messageId: string; actionsElement: HTMLElement; messageRoot: HTMLElement; hasPreview: boolean; previewText: string | null; overrideText: string | null }): string => {
    return [
        inputArguments.messageId,
        inputArguments.actionsElement.getAttribute('data-message-streaming') ?? '',
        inputArguments.actionsElement.getAttribute('data-user-input-required') ?? '',
        inputArguments.hasPreview ? 'preview' : 'placeholder',
        inputArguments.previewText ?? '',
        inputArguments.overrideText ?? '',
        inputArguments.actionsElement.getAttribute(STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE) ?? '',
        inputArguments.actionsElement.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) ?? '',
        inputArguments.actionsElement.getAttribute(STREAM_SPINNER_HAS_LOADING_ACTIVITY_ATTRIBUTE) ?? '',
        inputArguments.actionsElement.getAttribute(STREAM_SPINNER_HAS_RUNNING_LOADING_ACTIVITY_ATTRIBUTE) ?? '',
        inputArguments.actionsElement.getAttribute(STREAM_SPINNER_HAS_RUNNING_WAIT_ACTIVITY_ATTRIBUTE) ?? '',
        inputArguments.actionsElement.getAttribute(STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE) ?? '',
        hasSettledActionButtons(inputArguments.actionsElement) ? 'settled' : 'live',
        hasVisibleSpinnerActivity(inputArguments.messageRoot) ? 'visible-activity' : 'no-visible-activity'
    ].join('|');
};

const canSkipStableSpinnerReconcile = (state: SpinnerStatusState, signature: string, hasPreview: boolean, expectedStableText: string | null): boolean => {
    if (state.lastReconcileSignature !== signature) {
        return false;
    }
    if (expectedStableText !== null && state.lastShownText !== expectedStableText) {
        return false;
    }
    if (state.visibilityRevealTimer !== null || state.visibilityFadeTimer !== null || state.firstRevealCleanupTimer !== null || state.checkpointTimer !== null || state.fadeTimer !== null) {
        return false;
    }
    if (state.pendingText !== null) {
        return false;
    }
    if (!hasPreview && state.placeholderRotationTimer === null) {
        return false;
    }
    return true;
};

export { canSkipStableSpinnerReconcile, resolveSpinnerReconcileSignature };
