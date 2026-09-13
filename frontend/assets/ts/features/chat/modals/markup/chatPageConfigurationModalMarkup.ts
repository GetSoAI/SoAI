/* SoAI - Chat feature page configuration modal markup [frontend/assets/ts/features/chat/modals/markup/chatPageConfigurationModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalBody, renderModalLoadingState, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import { buildAppearanceTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/appearance.ts';
import { buildCompletionTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/completion.ts';
import { buildFilesFolderTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/filesFolder.ts';
import { buildGeneralTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/chatConfigurationGeneralTab.ts';
import { buildKnowledgeTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/knowledge.ts';
import { buildMcpTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/mcp.ts';
import { buildMemoryTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/memory.ts';
import { buildPresetsTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/presets.ts';
import { buildVoiceTabMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/voice.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildChatConfigurationModalMarkup = (context: ChatPageMarkupContext): TrustedHtml => {
    const { strings } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiId(token);

    const header = renderStandardModalHeader({
        modalId,
        title: strings.configurationTitle,
        description: i18n.t('common.modalDescriptions.chatConfiguration'),
        closeLabel: strings.closeLabel,
        sections: uiHtml`<div id="${uiIdAttr('tabs')}"></div>`
    });

    const bodyMarkup = [buildGeneralTabMarkup(context), buildAppearanceTabMarkup(context), buildCompletionTabMarkup(context), buildVoiceTabMarkup(context), buildFilesFolderTabMarkup(context), buildKnowledgeTabMarkup(context), buildMemoryTabMarkup(context), buildMcpTabMarkup(context), buildPresetsTabMarkup(context)].join('');

    const body = renderModalBody(uiHtml`<div class="chat-configuration-scroll">${toTrustedHtml(bodyMarkup)}</div>${renderModalLoadingState({ text: i18n.t('common.loading'), overlay: true, className: 'chat-configuration-loading' })}`);

    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: strings.close, ariaLabel: strings.closeLabel }),
        right: renderModalFooterActionButton({ text: strings.saveCommon, ariaLabel: strings.titleSave, variant: 'accent', action: 'chat:save-configuration', className: 'chat-configuration-save-btn', disabled: true })
    });

    return renderModalScaffoldMarkup({ id: modalId, header, body, footer, rootAttributes: { 'data-page-scope': 'chat' } });
};

export { buildChatConfigurationModalMarkup };
