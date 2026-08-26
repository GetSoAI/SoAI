/* SoAI - Chat message DOM ownership verification [frontend/assets/ts/features/chat/message/messageDomOwnership.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';

type ChatMessageDomOwnershipArguments = {
    liveContainer: Element;
    messageRoot: Element | null;
    messageDomId: string;
    messageText?: Element | null;
};

const isElementInsideContainer = (container: Element, element: Element): boolean => {
    return container === element || container.contains(element);
};

const isChatMessageDomOwnedByLiveContainer = (inputArguments: ChatMessageDomOwnershipArguments): boolean => {
    const root = inputArguments.messageRoot;
    if (!(root instanceof HTMLElement) || !root.isConnected) {
        return false;
    }
    if (!isElementInsideContainer(inputArguments.liveContainer, root)) {
        return false;
    }
    const expectedDomId = normalizeMessageDomId(inputArguments.messageDomId);
    if (!expectedDomId || normalizeMessageDomId(root.getAttribute('data-id') ?? '') !== expectedDomId) {
        return false;
    }
    if (inputArguments.messageText !== undefined && inputArguments.messageText !== null) {
        const textRoot = inputArguments.messageText;
        if (!(textRoot instanceof HTMLElement) || !textRoot.isConnected) {
            return false;
        }
        if (!root.contains(textRoot) || !isElementInsideContainer(inputArguments.liveContainer, textRoot)) {
            return false;
        }
    }
    return true;
};

export { isChatMessageDomOwnedByLiveContainer };
