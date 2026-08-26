/* SoAI - Shared chat parameter editor modal markup [frontend/assets/ts/core/chat/parameters/parameterEditorModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderChatParameterControlsMarkup } from '@core/chat/parameters/parameterControlsMarkup.ts';
import { CHAT_PARAMETER_ACTION_OPEN_MODEL_SETTINGS, renderModelParameterNavigationMarkup } from '@core/chat/parameters/modelParameterNavigationMarkup.ts';
import { resolveChatParameterControlStrings } from '@core/chat/parameters/parameterControlStrings.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { renderModalBody, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';

type ChatParameterEditorModalMarkupOptions = {
    modalId: string;
    title: string;
    description: string;
    closeLabel: string;
    cancelLabel: string;
    saveLabel: string;
    pageScope: string;
    includeSystemPromptLock: boolean;
};

const CHAT_PARAMETER_EDITOR_ACTION_SAVE = 'chat-parameters:save';

const renderChatParameterEditorModalMarkup = (options: ChatParameterEditorModalMarkupOptions): TrustedHtml => {
    const header = renderStandardModalHeader({
        modalId: options.modalId,
        title: options.title,
        description: options.description,
        closeLabel: options.closeLabel
    });
    const body = renderModalBody(
        uiHtml`
            <div class="chat-config-grid">
                ${toTrustedHtml(
                    renderChatParameterControlsMarkup({
                        modalId: options.modalId,
                        strings: resolveChatParameterControlStrings(),
                        includeSystemPromptLock: options.includeSystemPromptLock
                    })
                )}
                ${renderModelParameterNavigationMarkup(CHAT_PARAMETER_ACTION_OPEN_MODEL_SETTINGS)}
            </div>
        `,
        { className: 'chat-parameter-editor-modal-body' }
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({
            modalId: options.modalId,
            text: options.cancelLabel
        }),
        right: renderModalFooterActionButton({
            text: options.saveLabel,
            id: modalUiId(options.modalId, 'save-button'),
            variant: 'accent',
            action: CHAT_PARAMETER_EDITOR_ACTION_SAVE,
            disabled: true
        })
    });
    return renderModalScaffoldMarkup({
        id: options.modalId,
        header,
        body,
        footer,
        contentClassName: 'chat-configuration-modal chat-parameter-editor-modal',
        rootAttributes: { 'data-page-scope': options.pageScope }
    });
};

export { renderChatParameterEditorModalMarkup };
export type { ChatParameterEditorModalMarkupOptions };
