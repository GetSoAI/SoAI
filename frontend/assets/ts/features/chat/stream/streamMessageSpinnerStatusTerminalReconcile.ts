/* SoAI - Streaming spinner status terminal teardown reconciliation [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusTerminalReconcile.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { withAssistantViewportStability } from '@features/chat/message/assistantViewportStability.ts';
import { animatePresenceExit } from '@core/animations/presence/public.ts';
import { STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { requireStatusTextBodyElement, requireStatusTextElement, resolveActionButtonsLeftElement, resolveMessageId, resolveOwningMessageRoot, resolveSpinnerElement, resolveStreamingStatusElement } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';
import { FIRST_REVEAL_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusFirstReveal.ts';
import { clearStateTimers, createSpinnerStatusState, getRuntimeStateByMessageId, setRuntimeStateByMessageId, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { clearSpinnerStatusRuntimeText, FADING_CLASS, finalizeState, finishStatusTextTransitionElement, VISIBILITY_FADING_CLASS } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { chooseNextKey } from '@features/chat/stream/streamMessageSpinnerStatusText.ts';

const resolveTerminalState = (actions: HTMLElement, status: HTMLElement): SpinnerStatusState | null => {
    const root = resolveOwningMessageRoot(status);
    const messageId = resolveMessageId(root);
    const existing = getRuntimeStateByMessageId(actions.ownerDocument, messageId);
    if (existing !== undefined && existing.actionsElement === actions) return existing;
    const view = actions.ownerDocument.defaultView;
    if (view === null) return null;
    const label = requireStatusTextElement(status);
    const text = requireStatusTextBodyElement(label);
    const state = createSpinnerStatusState({ messageId, messageRoot: root, statusElement: status, labelElement: label, textElement: text, actionsElement: actions, spinnerElement: resolveSpinnerElement(actions), view, visibilityRevealAtServerMs: 0, placeholderKey: chooseNextKey(null), lastShownText: text.textContent ?? '', hasShownRealPreview: actions.getAttribute(STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE) === 'true' });
    setRuntimeStateByMessageId(actions.ownerDocument, messageId, state);
    return state;
};

const isSpinnerStatusTerminalTransitionActive = (actions: HTMLElement): boolean => {
    const status = resolveStreamingStatusElement(actions);
    if (status === null) return false;
    const state = getRuntimeStateByMessageId(actions.ownerDocument, resolveMessageId(resolveOwningMessageRoot(status)));
    return state?.actionsElement === actions && state.terminalTransitionActive;
};

const beginTerminalExit = (state: SpinnerStatusState): void => {
    const actions = state.actionsElement;
    const status = state.statusElement;
    const label = state.labelElement;
    const text = state.textElement;
    if (actions === null || status === null || label === null || text === null) throw new Error('Terminal status requires its canonical surfaces.');
    const group = resolveActionButtonsLeftElement(actions);
    const view = actions.ownerDocument.defaultView;
    const fromOpacity = view === null ? 1 : Number(view.getComputedStyle(group).opacity) * Math.min(Number(view.getComputedStyle(text).opacity), state.spinnerElement === null ? 1 : Number(view.getComputedStyle(state.spinnerElement).opacity));
    clearStateTimers(state);
    state.terminalTransitionActive = true;
    actions.setAttribute('data-message-streaming', 'false');
    text.classList.remove(VISIBILITY_FADING_CLASS);
    state.spinnerElement?.classList.remove(FADING_CLASS);
    group.setAttribute('data-presence-atomic', '');
    group.setAttribute('data-presence-visual-only', '');
    const animation = animatePresenceExit(group, true, { fromOpacity });
    const finish = (): void => {
        animation?.removeEventListener('finish', finish);
        animation?.removeEventListener('cancel', finish);
        if (getRuntimeStateByMessageId(actions.ownerDocument, state.messageId) !== state) return;
        const applySettledActions = state.pendingSettledActions;
        withAssistantViewportStability(actions, () => {
            actions.setAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE, 'false');
            actions.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
            clearSpinnerStatusRuntimeText(status, label, text, actions);
            finalizeState(actions.ownerDocument, state);
            animation?.cancel();
            if (actions.isConnected) applySettledActions?.();
        });
    };
    if (animation === null) finish();
    else {
        animation.addEventListener('finish', finish);
        animation.addEventListener('cancel', finish);
    }
};

const deferSettledActionsUntilSpinnerExit = (actions: HTMLElement, applySettledActions: () => void): boolean => {
    const status = resolveStreamingStatusElement(actions);
    if (status === null || actions.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) !== 'true') return false;
    const state = resolveTerminalState(actions, status);
    if (state === null) return false;
    state.pendingSettledActions = applySettledActions;
    if (!state.terminalTransitionActive) beginTerminalExit(state);
    return true;
};

const cancelSpinnerStatusTerminalTransition = (actions: HTMLElement): void => {
    const status = resolveStreamingStatusElement(actions);
    if (status === null) return;
    const state = getRuntimeStateByMessageId(actions.ownerDocument, resolveMessageId(resolveOwningMessageRoot(status)));
    if (state?.actionsElement === actions && state.terminalTransitionActive) finalizeState(actions.ownerDocument, state);
};

const reconcileNonStreamingSpinnerStatusElement = (inputArguments: { documentRef: Document; state: SpinnerStatusState | null; statusElement: HTMLElement; labelElement: HTMLElement; actionsElement: HTMLElement; bodyElement: HTMLElement }): void => {
    const { documentRef, state, statusElement, labelElement, actionsElement, bodyElement } = inputArguments;
    if (state?.actionsElement === actionsElement && state.terminalTransitionActive) return;
    if (actionsElement.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) === 'true') {
        const terminal = resolveTerminalState(actionsElement, statusElement);
        if (terminal !== null) {
            beginTerminalExit(terminal);
            return;
        }
    }
    actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
    actionsElement.setAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE, 'false');
    finishStatusTextTransitionElement(bodyElement);
    bodyElement.classList.remove(VISIBILITY_FADING_CLASS);
    clearSpinnerStatusRuntimeText(statusElement, labelElement, bodyElement, actionsElement);
    if (state !== null) finalizeState(documentRef, state);
};

export { cancelSpinnerStatusTerminalTransition, deferSettledActionsUntilSpinnerExit, isSpinnerStatusTerminalTransitionActive, reconcileNonStreamingSpinnerStatusElement };
