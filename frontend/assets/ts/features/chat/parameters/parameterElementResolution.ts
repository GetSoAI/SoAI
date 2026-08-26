/* SoAI - Chat feature parameter element resolution [frontend/assets/ts/features/chat/parameters/parameterElementResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ChatParameterControlElement = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

const isChatParameterControlElement = (element: Element | null): element is ChatParameterControlElement => {
    return element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement;
};

const resolveChatParameterControlElement = (target: Element): ChatParameterControlElement | null => {
    const parameterTarget = target.closest('[data-param]');
    return isChatParameterControlElement(parameterTarget) ? parameterTarget : null;
};

export { isChatParameterControlElement, resolveChatParameterControlElement };
export type { ChatParameterControlElement };
