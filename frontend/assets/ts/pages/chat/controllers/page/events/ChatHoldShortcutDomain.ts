/* SoAI - Chat hold shortcut action binding [frontend/assets/ts/pages/chat/controllers/page/events/ChatHoldShortcutDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindHoldGesture, type ActiveHoldGesture, type HoldGestureAction, type HoldGesturePointerContext } from '@core/dom/holdGestureBinding.ts';
import { CHAT_ACTIONS, isMcpToolsSettingsNavigationAllowed } from '@features/chat/public.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { isActionElementDisabled } from '@pages/chat/controllers/page/events/dispatch.ts';

type ChatHoldShortcutAction = typeof CHAT_ACTIONS.CYCLE_TOKEN_COUNTER | typeof CHAT_ACTIONS.TOGGLE_TOOLS | typeof CHAT_ACTIONS.TOGGLE_CONFIGURATION | typeof CHAT_ACTIONS.TOGGLE_RECORDING;
type ChatHoldShortcutHost = Pick<ChatRootEventsHost, 'holdShortcuts'>;

const isChatHoldShortcutAction = (value: string | undefined): value is ChatHoldShortcutAction => value === CHAT_ACTIONS.CYCLE_TOKEN_COUNTER || value === CHAT_ACTIONS.TOGGLE_TOOLS || value === CHAT_ACTIONS.TOGGLE_CONFIGURATION || value === CHAT_ACTIONS.TOGGLE_RECORDING;

const beginPushToTalk = (host: ChatHoldShortcutHost, context: HoldGesturePointerContext<ChatHoldShortcutAction>): ActiveHoldGesture<ChatHoldShortcutAction> | null => {
    if (!(context.actionElement instanceof HTMLButtonElement)) return null;
    const snapshot = host.holdShortcuts.captureDraftSurface();
    const session = host.holdShortcuts.beginPushToTalk(context.actionElement, context.start, snapshot);
    if (!session) return null;
    return {
        move: (next) => session.move(next.current),
        release: (next) => session.release(next.current),
        cancel: () => session.cancel(false)
    };
};

const resolveChatHoldShortcut = (host: ChatHoldShortcutHost, action: ChatHoldShortcutAction, actionElement: HTMLElement): HoldGestureAction<ChatHoldShortcutAction> => {
    if (action === CHAT_ACTIONS.CYCLE_TOKEN_COUNTER) {
        return { isEligible: () => !isActionElementDisabled(actionElement), activate: () => (host.holdShortcuts.openConfiguration('completion', 'context-window'), {}) };
    }
    if (action === CHAT_ACTIONS.TOGGLE_TOOLS) {
        return { isEligible: () => isMcpToolsSettingsNavigationAllowed(actionElement), activate: () => (host.holdShortcuts.openConfiguration('mcp'), {}) };
    }
    if (action === CHAT_ACTIONS.TOGGLE_CONFIGURATION) {
        return { isEligible: () => !isActionElementDisabled(actionElement), activate: () => (host.holdShortcuts.openConfiguration('presets'), {}) };
    }
    return {
        isEligible: () => !isActionElementDisabled(actionElement) && host.holdShortcuts.canStartPushToTalk(),
        activate: (context) => beginPushToTalk(host, context)
    };
};

const bindChatHoldShortcuts = (host: ChatHoldShortcutHost, root: HTMLElement, signal: AbortSignal): void => {
    bindHoldGesture<ChatHoldShortcutAction>({
        root,
        signal,
        isAction: isChatHoldShortcutAction,
        resolveAction: (action, actionElement) => resolveChatHoldShortcut(host, action, actionElement)
    });
};

export { bindChatHoldShortcuts, isChatHoldShortcutAction };
export type { ChatHoldShortcutAction };
