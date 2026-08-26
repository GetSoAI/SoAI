/* SoAI - Chat feature files folder [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/filesFolder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { buildWorkspaceFolderFieldMarkup } from '@core/fileexplorerbrowser/workspaceFolderFieldMarkup.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildFilesFolderTabMarkup = (context: ChatPageMarkupContext): string => {
    const { strings } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;

    return `
<div id="${uiIdAttr('files-folder-content')}" class="tab-content chat-config-files-folder-tab">
  <div class="chat-config-grid">
    ${
        buildWorkspaceFolderFieldMarkup({
            pathInputId: uiId('chat-files-folder-path'),
            changeButtonId: uiId('chat-files-folder-change-btn'),
            statusId: uiId('chat-files-folder-status'),
            label: strings.filesFolderCurrentLabel,
            buttonLabel: strings.filesFolderChangeButton,
            description: strings.filesFolderDescription
        }).html
    }
  </div>
</div>
`;
};

export { buildFilesFolderTabMarkup };
