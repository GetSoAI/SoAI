/* SoAI - Chat page handlers [frontend/assets/ts/pages/chat/controllers/page/events/handlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isElementNode } from '@core/typeGuards.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { CHAT_ACTIONS, isMarkdownTableHeaderLinkTarget, optionalSecretPromptRootFromChild, resolveChatParameterControlElement, setSecretPromptLabelVisibility, type ChatActionId } from '@features/chat/public.ts';
import { hasInputSoaiPathToken } from '@pages/chat/controllers/chatmessagesendingcontroller/soaiLinkInputController.ts';
import { CHAT_MODEL_CONTROL_ROOT_SELECTOR } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts';
import { CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuSearchWidget.ts';
import { resolveChatMessageHoverTransition } from '@pages/chat/controllers/page/events/chatMessageHoverTransitions.ts';
import { resolveChatInputTarget } from '@pages/chat/controllers/page/events/chatInputTargetController.ts';
import { refreshChatInputUiState } from '@pages/chat/controllers/page/dom/input.ts';
import { handleConversationRenameBlur, handleConversationRenameInput } from '@pages/chat/controllers/page/events/events.ts';
import { handleRootKeydown } from '@pages/chat/controllers/page/events/keyboardController.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { dispatchResolvedActionCandidate, isPrimaryPointerInteraction } from '@pages/chat/controllers/page/events/dispatch.ts';
import { resolveNormalizedMessageIdForTarget } from '@pages/chat/controllers/page/events/messageTargetResolutionController.ts';

type RootChangeRoute = {
    taskId: string;
    matches: (target: Element) => boolean;
    run: (host: ChatRootEventsHost, event: Event) => Promise<void> | void;
};

const resolveNonModalTarget = (event: Event): Element | null => {
    const target = event.target;
    if (!isElementNode(target)) {
        return null;
    }
    return target;
};

const runParameterValueTask = (host: ChatRootEventsHost, target: Element, taskId: 'chat:parameterInput' | 'chat:parameterChange'): void => {
    const parameterTarget = resolveChatParameterControlElement(target);
    if (parameterTarget) {
        host.shell.runUiTask(taskId, () => host.composer.applyParameterValueFromElement(parameterTarget));
    }
};

const runMatchedChangeTask = (host: ChatRootEventsHost, target: Element, route: RootChangeRoute, event: Event): boolean => {
    if (!route.matches(target)) {
        return false;
    }
    host.shell.runUiTask(route.taskId, () => route.run(host, event));
    return true;
};

const ROOT_CHANGE_ROUTES: RootChangeRoute[] = [
    {
        taskId: 'chat:fileUpload',
        matches: (target: Element) => target.matches('.file-upload-input'),
        run: (host, event) => host.composer.handleFileUpload(event)
    },
    {
        taskId: 'chat:folderUpload',
        matches: (target: Element) => target.matches('.folder-upload-input'),
        run: (host, event) => host.composer.handleFolderUpload(event)
    },
    {
        taskId: 'chat:agentModeSelect',
        matches: (target: Element) => target.matches('.chat-page-mode-indicator-select'),
        run: (host, event) => host.composer.handleAgentModeSelectChange(event)
    },
    {
        taskId: 'chat:secretPromptSaveToggle',
        matches: (target: Element) => target.matches('.secret-prompt-save-checkbox'),
        run: (_host, event) => {
            const saveToggle = event.target;
            if (!(saveToggle instanceof HTMLInputElement) || saveToggle.type !== 'checkbox') {
                throw new TypeError('Vault secret prompt save toggle must be a checkbox input');
            }
            updateToggleLabel(saveToggle, { checked: saveToggle.checked });
            const root = optionalSecretPromptRootFromChild(saveToggle);
            if (!root) {
                return;
            }
            setSecretPromptLabelVisibility(root, saveToggle.checked);
        }
    }
];

const handleRootPointerHoverChange = (host: ChatRootEventsHost, event: Event, hovering: boolean): void => {
    const transition = resolveChatMessageHoverTransition(event, hovering);
    if (!transition) {
        return;
    }
    const normalizedMessageId = resolveNormalizedMessageIdForTarget(host, transition.messageRoot);
    if (!normalizedMessageId) {
        return;
    }
    host.shell.handleChatMessageHoverChange(normalizedMessageId, hovering);
};

const handleRootBackgroundClick = (host: ChatRootEventsHost, target: Element): void => {
    if (!target.closest('.chat-conversation-color-picker') && !target.closest('.color-picker-trigger')) {
        host.shell.hideConversationColorPicker();
    }
    if (target.closest('.chat-input')) {
        host.shell.collapseSidebarIfNarrowViewport();
        return;
    }
    host.shell.handleMobileSidebarClickAway(target);
};

const handleRootBackgroundPointerDown = (host: ChatRootEventsHost, event: Event): void => {
    const target = event.target;
    if (!isElementNode(target)) {
        return;
    }
    if (!target.closest(CHAT_MODEL_CONTROL_ROOT_SELECTOR)) {
        host.shell.closeChatModelControlMenu();
    }
    handleRootBackgroundClick(host, target);
};

const handleRootActionClick = (host: ChatRootEventsHost, event: Event, action: ChatActionId, actionElement: HTMLElement): void => {
    if (event.defaultPrevented) {
        return;
    }
    if (action === CHAT_ACTIONS.SORT_MARKDOWN_TABLE && isMarkdownTableHeaderLinkTarget(event.target, actionElement)) {
        return;
    }
    if (actionElement instanceof HTMLInputElement || actionElement instanceof HTMLSelectElement || actionElement instanceof HTMLTextAreaElement) {
        return;
    }
    dispatchResolvedActionCandidate(host, event, { actionElement, action });
};

const createRootPointerHoverHandler = (hovering: boolean): ((host: ChatRootEventsHost, event: Event) => void) => {
    return (host: ChatRootEventsHost, event: Event): void => {
        handleRootPointerHoverChange(host, event, hovering);
    };
};

const handleRootPointerDown = (host: ChatRootEventsHost, event: Event): void => {
    if (!isPrimaryPointerInteraction(event)) {
        return;
    }
    handleRootBackgroundPointerDown(host, event);
};

const handleChatInputChange = (host: ChatRootEventsHost, input: HTMLTextAreaElement): void => {
    const inputValue = input.value;
    refreshChatInputUiState(host.composer, input);
    host.composer.draft.noteChanged(inputValue);
    if (inputValue.length > 0) {
        host.shell.collapseSidebarIfNarrowViewport();
    }
    if (hasInputSoaiPathToken(inputValue)) {
        host.shell.runUiTask('chat:resolveInputSoaiLinks', () => host.composer.resolveSoaiLinksFromInput(input, inputValue));
    }
};

const handleRootPointerOver = createRootPointerHoverHandler(true);
const handleRootPointerOut = createRootPointerHoverHandler(false);

const handleRootInput = (host: ChatRootEventsHost, event: Event): void => {
    const target = resolveNonModalTarget(event);
    if (!target) {
        return;
    }
    const chatInput = resolveChatInputTarget(target);
    if (chatInput) {
        handleChatInputChange(host, chatInput);
        return;
    }
    if (handleConversationRenameInput(host, target)) {
        return;
    }
    if (target instanceof HTMLInputElement && target.matches(CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR)) {
        host.shell.handleChatModelControlSearchInput(target);
        return;
    }
    runParameterValueTask(host, target, 'chat:parameterInput');
};

const handleRootChange = (host: ChatRootEventsHost, event: Event): void => {
    const target = resolveNonModalTarget(event);
    if (!target) {
        return;
    }
    for (const route of ROOT_CHANGE_ROUTES) {
        if (runMatchedChangeTask(host, target, route, event)) {
            return;
        }
    }
    runParameterValueTask(host, target, 'chat:parameterChange');
};

const handleRootBlur = (host: ChatRootEventsHost, event: Event): void => {
    const target = resolveNonModalTarget(event);
    if (target && resolveChatInputTarget(target)) {
        host.shell.runUiTask('chat:composerDraftBlur', () => host.composer.draft.flush('blur'));
        return;
    }
    handleConversationRenameBlur(host, event.target, event);
};

export { handleRootActionClick, handleRootBlur, handleRootChange, handleRootInput, handleRootKeydown, handleRootPointerDown, handleRootPointerOut, handleRootPointerOver };
