/* SoAI - Chat feature strings basics [frontend/assets/ts/features/chat/chattemplates/chatStringsBasics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatTemplateStringSet } from '@features/chat/chattemplates/stringSetTypes.ts';

type Basics = Pick<ChatTemplateStringSet, 'selectModel' | 'newChat' | 'toggleSidebar' | 'toggleFavorites' | 'newConversation' | 'newTitle' | 'configuration' | 'exportAction' | 'gotoPrompts' | 'openCharacterMap' | 'toggleTools' | 'toggleFavorite' | 'tokenCounterTooltip' | 'tokenCounterInactive' | 'inputPlaceholder' | 'attachAdd' | 'openCamera' | 'startRecording' | 'stopRecording' | 'voiceCallStart' | 'send' | 'stop'>;

const resolveBasicsTemplateStrings = (sanitizer: SanitizerApi): Basics => {
    return {
        selectModel: i18n.html(sanitizer, 'chat.sidebar.selectModel'),
        newChat: i18n.html(sanitizer, 'chat.sidebar.newChat'),
        toggleSidebar: i18n.attr(sanitizer, 'chat.header.toggleSidebar'),
        toggleFavorites: i18n.attr(sanitizer, 'chat.sidebar.toggleFavorites'),
        newConversation: i18n.attr(sanitizer, 'chat.header.newConversation'),
        newTitle: i18n.html(sanitizer, 'chat.conversation.newTitle'),
        configuration: i18n.attr(sanitizer, 'chat.header.configuration'),
        exportAction: i18n.attr(sanitizer, 'chat.header.export'),
        gotoPrompts: i18n.attr(sanitizer, 'chat.header.gotoPrompts'),
        openCharacterMap: i18n.attr(sanitizer, 'chat.characterMap.open'),
        toggleTools: i18n.attr(sanitizer, 'chat.header.toggleTools'),
        toggleFavorite: i18n.attr(sanitizer, 'chat.header.toggleFavorite'),
        tokenCounterTooltip: i18n.attr(sanitizer, 'chat.tokenCounter.tooltip'),
        tokenCounterInactive: i18n.html(sanitizer, 'chat.tokenCounter.inactive'),
        inputPlaceholder: i18n.attr(sanitizer, 'chat.input.placeholder'),
        attachAdd: i18n.attr(sanitizer, 'chat.input.attachAdd'),
        openCamera: i18n.attr(sanitizer, 'chat.input.openCamera'),
        startRecording: i18n.attr(sanitizer, 'chat.input.startRecording'),
        stopRecording: i18n.attr(sanitizer, 'chat.input.stopRecording'),
        voiceCallStart: i18n.attr(sanitizer, 'chat.input.voiceCallStart'),
        send: i18n.attr(sanitizer, 'chat.input.send'),
        stop: i18n.attr(sanitizer, 'chat.input.stop')
    };
};

export { resolveBasicsTemplateStrings };
