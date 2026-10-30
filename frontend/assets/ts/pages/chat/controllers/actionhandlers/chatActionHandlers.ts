/* SoAI - Chat page action handlers [frontend/assets/ts/pages/chat/controllers/actionhandlers/chatActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_ACTIONS, readChatMultimediaPreviewDataset, requireChatMultimediaPreviewUrl, type ChatActionId } from '@features/chat/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { downloadUrl, triggerDownloadLink } from '@core/primitives/download.ts';
import { createChatAskUserActionHandlers } from '@pages/chat/controllers/actionhandlers/chatAskUserActionHandlers.ts';
import { createChatSecretPromptActionHandlers } from '@pages/chat/controllers/actionhandlers/chatSecretPromptActionHandlersController.ts';
import { createChatMessageActionHandlers } from '@pages/chat/controllers/actionhandlers/chatMessageActionHandlers.ts';
import { createChatMarkdownTableActionHandlers } from '@pages/chat/controllers/actionhandlers/chatMarkdownTableActionController.ts';
import { createChatToolApprovalActionHandlers } from '@pages/chat/controllers/actionhandlers/toolapproval/actions.ts';
import { createChatAgentActionHandlers } from '@pages/chat/controllers/actionhandlers/core/agentActionHandlers.ts';
import { createChatComposerActionHandlers } from '@pages/chat/controllers/actionhandlers/core/composerActionHandlers.ts';
import type { ChatActionHandler, ChatActionHandlersHost } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import { createChatConversationListActionHandlers } from '@pages/chat/controllers/actionhandlers/core/conversationListActionHandlers.ts';
import { createChatShellActionHandlers } from '@pages/chat/controllers/actionhandlers/core/shellActionHandlers.ts';

const createChatActionHandlers = (host: ChatActionHandlersHost): Record<ChatActionId, ChatActionHandler> => ({
    [CHAT_ACTIONS.FIND_OPEN]: () => host.presentation.find(CHAT_ACTIONS.FIND_OPEN),
    [CHAT_ACTIONS.FIND_CLOSE]: () => host.presentation.find(CHAT_ACTIONS.FIND_CLOSE),
    [CHAT_ACTIONS.FIND_PREVIOUS]: () => host.presentation.find(CHAT_ACTIONS.FIND_PREVIOUS),
    [CHAT_ACTIONS.FIND_NEXT]: () => host.presentation.find(CHAT_ACTIONS.FIND_NEXT),
    [CHAT_ACTIONS.FIND_RETRY]: () => host.presentation.find(CHAT_ACTIONS.FIND_RETRY),
    ...createChatShellActionHandlers(host),
    ...createChatComposerActionHandlers(host),
    ...createChatConversationListActionHandlers(host),
    [CHAT_ACTIONS.COMPARISON_PREV]: (actionElement: HTMLElement): void => host.presentation.handleComparisonNavigation(actionElement),
    [CHAT_ACTIONS.COMPARISON_NEXT]: (actionElement: HTMLElement): void => host.presentation.handleComparisonNavigation(actionElement),
    [CHAT_ACTIONS.MODEL_CONTROL_TOGGLE_MENU]: (actionElement: HTMLElement): void => host.presentation.handleModelControlAction(actionElement),
    [CHAT_ACTIONS.MODEL_CONTROL_SELECT_MODEL]: (actionElement: HTMLElement): void => host.presentation.handleModelControlAction(actionElement),
    [CHAT_ACTIONS.MODEL_CONTROL_ADD_MODEL]: (actionElement: HTMLElement): void => host.presentation.handleModelControlAction(actionElement),
    [CHAT_ACTIONS.MODEL_CONTROL_REMOVE_MODEL]: (actionElement: HTMLElement): void => host.presentation.handleModelControlAction(actionElement),
    [CHAT_ACTIONS.DOWNLOAD_MULTIMEDIA]: (actionElement: HTMLElement, event: Event): void => {
        if (!(actionElement instanceof HTMLAnchorElement)) {
            throw new TypeError('Chat multimedia download action must be an anchor');
        }
        event.preventDefault();
        if (actionElement.hasAttribute('data-media-type')) {
            const media = readChatMultimediaPreviewDataset(actionElement);
            triggerDownloadLink({ href: media.downloadUrl ?? requireChatMultimediaPreviewUrl(media, 'download'), ...(media.downloadName === null ? {} : { filename: media.downloadName }), forceDownload: true });
        } else downloadUrl(actionElement.href);
        host.shared.feedback.show(i18n.t('common.notifications.downloadStarted'), 'download');
    },
    [CHAT_ACTIONS.OPEN_MULTIMEDIA_SOURCE]: (actionElement: HTMLElement, event: Event): void => host.presentation.dispatchMessageAction(actionElement, CHAT_ACTIONS.OPEN_MULTIMEDIA_SOURCE, event),
    ...createChatAgentActionHandlers(host),
    ...createChatMarkdownTableActionHandlers(),
    ...createChatMessageActionHandlers(host),
    ...createChatAskUserActionHandlers(host),
    ...createChatSecretPromptActionHandlers(host),
    ...createChatToolApprovalActionHandlers(host)
});

export { createChatActionHandlers };
export type { ChatActionHandlersHost };
