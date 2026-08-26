/* SoAI - Chat page events [frontend/assets/ts/pages/chat/controllers/page/events/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isElementNode } from '@core/typeGuards.ts';
import { resolveInlineTextEditKeyAction } from '@core/ui/inlineedit/controller.ts';
import { limitConversationTitleLength } from '@features/chat/public.ts';

interface ChatConversationRenameEventsHost {
    shell: {
        runUiTask: (taskId: string, task: () => void) => void;
    };
    conversations: {
        updateConversationRenameDraft: (value: string) => void;
        saveConversationTitleRename: () => void;
        cancelConversationTitleRename: () => void;
        saveConversationListTitleRename: () => void;
        cancelConversationListTitleRename: () => void;
        handleConversationTitleBlur: (event: Event) => void;
        handleConversationListTitleBlur: (event: Event) => void;
    };
}

type ConversationRenameTargetType = 'conversation' | 'conversation-list';

type ConversationRenameTaskId = 'chat:conversationTitleSaveHotkey' | 'chat:conversationListTitleSaveHotkey' | 'chat:conversationTitleBlur' | 'chat:conversationListTitleBlur';

type ConversationRenameActions = {
    saveTaskId: ConversationRenameTaskId;
    blurTaskId: ConversationRenameTaskId;
    save: () => void;
    cancel: () => void;
    blur: (event: Event) => void;
};

const resolveConversationRenameTargetType = (target: EventTarget | null): ConversationRenameTargetType | null => {
    if (!isElementNode(target)) {
        return null;
    }
    if (target.matches('.conversation-title-input')) {
        return 'conversation';
    }
    if (target.matches('.conversation-item-title-input')) {
        return 'conversation-list';
    }
    return null;
};

const resolveConversationRenameActions = (host: ChatConversationRenameEventsHost, targetType: ConversationRenameTargetType): ConversationRenameActions => {
    if (targetType === 'conversation') {
        return {
            saveTaskId: 'chat:conversationTitleSaveHotkey',
            blurTaskId: 'chat:conversationTitleBlur',
            save: () => host.conversations.saveConversationTitleRename(),
            cancel: () => host.conversations.cancelConversationTitleRename(),
            blur: (event) => host.conversations.handleConversationTitleBlur(event)
        };
    }
    return {
        saveTaskId: 'chat:conversationListTitleSaveHotkey',
        blurTaskId: 'chat:conversationListTitleBlur',
        save: () => host.conversations.saveConversationListTitleRename(),
        cancel: () => host.conversations.cancelConversationListTitleRename(),
        blur: (event) => host.conversations.handleConversationListTitleBlur(event)
    };
};

const resolveConversationRenameActionsForTarget = (host: ChatConversationRenameEventsHost, target: EventTarget | null): ConversationRenameActions | null => {
    const targetType = resolveConversationRenameTargetType(target);
    if (targetType === null) {
        return null;
    }
    return resolveConversationRenameActions(host, targetType);
};

const handleConversationRenameInput = (host: ChatConversationRenameEventsHost, target: EventTarget | null): boolean => {
    const renameActions = resolveConversationRenameActionsForTarget(host, target);
    if (renameActions === null) {
        return false;
    }
    if (!(target instanceof HTMLInputElement)) {
        throw new TypeError('Chat conversation rename input must be an input element');
    }
    const draft = limitConversationTitleLength(target.value);
    if (target.value !== draft) {
        target.value = draft;
    }
    host.conversations.updateConversationRenameDraft(draft);
    return true;
};

const handleConversationRenameKeydown = (host: ChatConversationRenameEventsHost, target: EventTarget | null, event: KeyboardEvent): boolean => {
    const renameActions = resolveConversationRenameActionsForTarget(host, target);
    if (renameActions === null) {
        return false;
    }
    const action = resolveInlineTextEditKeyAction(event);
    if (action === 'save') {
        host.shell.runUiTask(renameActions.saveTaskId, renameActions.save);
        return true;
    }
    if (action === 'cancel') {
        renameActions.cancel();
        return true;
    }
    return false;
};

const handleConversationRenameBlur = (host: ChatConversationRenameEventsHost, target: EventTarget | null, event: Event): boolean => {
    const renameActions = resolveConversationRenameActionsForTarget(host, target);
    if (renameActions === null) {
        return false;
    }
    host.shell.runUiTask(renameActions.blurTaskId, () => renameActions.blur(event));
    return true;
};

export { handleConversationRenameBlur, handleConversationRenameInput, handleConversationRenameKeydown };
