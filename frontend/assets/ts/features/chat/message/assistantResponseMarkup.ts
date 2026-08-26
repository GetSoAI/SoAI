/* SoAI - Chat feature assistant response markup [frontend/assets/ts/features/chat/message/assistantResponseMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const ASSISTANT_ACTIVITY_WIDGETS_ATTRIBUTE = 'data-assistant-activity-widgets';

const buildAssistantResponseMarkup = (inputArguments: { bodyHtml: string }): string => {
    return `<div class="message-response">${inputArguments.bodyHtml}</div>`;
};

export { ASSISTANT_ACTIVITY_WIDGETS_ATTRIBUTE, buildAssistantResponseMarkup };
