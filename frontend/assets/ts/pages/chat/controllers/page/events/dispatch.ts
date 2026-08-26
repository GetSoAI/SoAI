/* SoAI - Chat page dispatch [frontend/assets/ts/pages/chat/controllers/page/events/dispatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveDelegatedActionElement } from '@core/dom/dataAction.ts';
import { isChatActionId, type ChatActionId } from '@features/chat/public.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';

const resolveActionDispatchCandidate = (event: Event, root: HTMLElement): { actionElement: HTMLElement; action: ChatActionId } | null => {
    if (!(event.target instanceof Node)) {
        return null;
    }
    const actionElement = resolveDelegatedActionElement({ event, root, preventDefault: 'never', ignoreFormControls: true });
    if (!(actionElement instanceof HTMLElement)) {
        return null;
    }
    const candidateAction = actionElement.dataset.action;
    if (!isChatActionId(candidateAction)) {
        return null;
    }
    return {
        actionElement,
        action: candidateAction
    };
};

const isPrimaryPointerInteraction = (event: Event): event is MouseEvent => {
    if (!(event instanceof MouseEvent)) {
        return false;
    }
    return event.button === 0;
};

const isActionElementDisabled = (actionElement: HTMLElement): boolean => {
    if (actionElement.getAttribute('aria-disabled') === 'true' || actionElement.getAttribute('data-toggle-disabled') === 'true') {
        return true;
    }
    if (actionElement instanceof HTMLButtonElement && actionElement.disabled) {
        return true;
    }
    return false;
};

const dispatchResolvedActionCandidate = (host: ChatRootEventsHost, event: Event, candidate: { actionElement: HTMLElement; action: ChatActionId }): boolean => {
    if (isActionElementDisabled(candidate.actionElement)) {
        event.preventDefault();
        event.stopPropagation();
        return true;
    }
    event.preventDefault();
    host.shell.dispatchDataAction(candidate.action, candidate.actionElement, event);
    return true;
};

const dispatchActionFromEventWithinRoot = (host: ChatRootEventsHost, event: Event, actionRoot: HTMLElement): boolean => {
    if (event.defaultPrevented) {
        return false;
    }
    const candidate = resolveActionDispatchCandidate(event, actionRoot);
    if (!candidate) {
        return false;
    }
    if (!actionRoot.contains(candidate.actionElement)) {
        return false;
    }
    return dispatchResolvedActionCandidate(host, event, candidate);
};

export { dispatchActionFromEventWithinRoot, dispatchResolvedActionCandidate, isActionElementDisabled, isPrimaryPointerInteraction, resolveActionDispatchCandidate };
