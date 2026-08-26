/* SoAI - Chat page shell action handlers [frontend/assets/ts/pages/chat/controllers/actionhandlers/core/shellActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { encodeSegment } from '@core/identifiers.ts';
import { MODELS_ACTION_DOWNLOAD_MODEL } from '@core/models/pageActions.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';
import { CHAT_ACTIONS } from '@features/chat/public.ts';
import { createMappedActionHandlers } from '@pages/chat/controllers/actionhandlers/core/effects.ts';
import type { ChatActionHandler, ChatComposerActionPort, ChatConfigurationActionPort, ChatConversationActionPort, ChatExecutionActionPort, ChatNavigationActionPort, ChatPresentationActionPort, ChatToolbarActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

interface ChatShellActionsHost {
    composer: ChatComposerActionPort;
    configuration: ChatConfigurationActionPort;
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
    navigation: ChatNavigationActionPort;
    presentation: ChatPresentationActionPort;
    toolbar: ChatToolbarActionPort;
}

type ChatShellActionId = typeof CHAT_ACTIONS.NEW_CONVERSATION | typeof CHAT_ACTIONS.TOGGLE_SIDEBAR | typeof CHAT_ACTIONS.TOGGLE_FAVORITES_AT_TOP | typeof CHAT_ACTIONS.TOGGLE_CONFIGURATION | typeof CHAT_ACTIONS.OPEN_FILES_FOLDER_SETTINGS | typeof CHAT_ACTIONS.OPEN_MEMORY_PROFILE | typeof CHAT_ACTIONS.REFRESH_MEMORY | typeof CHAT_ACTIONS.EXPORT_CONVERSATION | typeof CHAT_ACTIONS.GOTO_PROMPTS | typeof CHAT_ACTIONS.GOTO_SETTINGS_MCP | typeof CHAT_ACTIONS.GOTO_MODEL_SETTINGS | typeof CHAT_ACTIONS.GOTO_MODELS_DOWNLOAD | typeof CHAT_ACTIONS.REFRESH_PRESETS | typeof CHAT_ACTIONS.RESET_PRESETS | typeof CHAT_ACTIONS.NEW_PRESET | typeof CHAT_ACTIONS.APPLY_PRESET | typeof CHAT_ACTIONS.REPLACE_PRESET | typeof CHAT_ACTIONS.RENAME_PRESET | typeof CHAT_ACTIONS.REMOVE_PRESET | typeof CHAT_ACTIONS.SUBMIT_PRESET_EDITOR | typeof CHAT_ACTIONS.CANCEL_PRESET_EDITOR | typeof CHAT_ACTIONS.REVIEW_PRESET_EDITOR | typeof CHAT_ACTIONS.RESTORE_PARAMETER_DEFAULTS | typeof CHAT_ACTIONS.OPEN_MODEL_DETAIL;

const resolveEncodedModelPath = (modelId: string | null): string | null => {
    const normalizedId = toTrimmedString(modelId);
    if (!normalizedId) {
        return null;
    }
    return `model/${encodeSegment(normalizedId)}`;
};

const navigateToModelPath = (host: ChatShellActionsHost, modelId: string | null, query: Record<string, string> | null = null): boolean => {
    const modelPath = resolveEncodedModelPath(modelId);
    if (!modelPath) {
        return false;
    }
    if (query) {
        host.navigation.navigateWithQuery(modelPath, query);
        return true;
    }
    host.navigation.navigate(modelPath);
    return true;
};

const createModelNavigationHandler = (host: ChatShellActionsHost, resolveModelId: (actionElement: HTMLElement | null) => string | null, options: { query?: Record<string, string>; defaultPage?: string } = {}): ChatActionHandler => {
    return (actionElement: HTMLElement): void => {
        if (navigateToModelPath(host, resolveModelId(actionElement), options.query ?? null)) {
            return;
        }
        if (isString(options.defaultPage) && options.defaultPage) {
            host.navigation.navigate(options.defaultPage);
        }
    };
};

const exportCurrentConversationIfIdle = (host: ChatShellActionsHost): void => {
    const conversationId = host.conversation.currentId();
    if (conversationId !== null && host.conversation.isExecuting(conversationId)) {
        return;
    }
    host.conversation.export(null);
};

const createChatShellActionHandlers = (host: ChatShellActionsHost): Record<ChatShellActionId, ChatActionHandler> => {
    return {
        [CHAT_ACTIONS.NEW_CONVERSATION]: (actionElement) => {
            host.conversation.actions.handleNewConversationClick(actionElement);
            host.composer.requireInput().focus({ preventScroll: true });
        },
        ...createMappedActionHandlers<Extract<ChatShellActionId, typeof CHAT_ACTIONS.TOGGLE_SIDEBAR | typeof CHAT_ACTIONS.TOGGLE_FAVORITES_AT_TOP | typeof CHAT_ACTIONS.TOGGLE_CONFIGURATION | typeof CHAT_ACTIONS.OPEN_FILES_FOLDER_SETTINGS | typeof CHAT_ACTIONS.OPEN_MEMORY_PROFILE | typeof CHAT_ACTIONS.EXPORT_CONVERSATION | typeof CHAT_ACTIONS.GOTO_PROMPTS | typeof CHAT_ACTIONS.GOTO_SETTINGS_MCP | typeof CHAT_ACTIONS.GOTO_MODELS_DOWNLOAD | typeof CHAT_ACTIONS.RESTORE_PARAMETER_DEFAULTS>>({
            [CHAT_ACTIONS.TOGGLE_SIDEBAR]: () => host.presentation.toggleSidebar(),
            [CHAT_ACTIONS.TOGGLE_FAVORITES_AT_TOP]: () => host.presentation.toggleFavoritesAtTop(),
            [CHAT_ACTIONS.TOGGLE_CONFIGURATION]: () => host.configuration.toggle(),
            [CHAT_ACTIONS.OPEN_FILES_FOLDER_SETTINGS]: () => host.configuration.openTab('files'),
            [CHAT_ACTIONS.OPEN_MEMORY_PROFILE]: () => host.configuration.openMemoryProfile(),
            [CHAT_ACTIONS.EXPORT_CONVERSATION]: () => exportCurrentConversationIfIdle(host),
            [CHAT_ACTIONS.GOTO_PROMPTS]: () => host.toolbar.openPrompts(),
            [CHAT_ACTIONS.GOTO_SETTINGS_MCP]: () => host.navigation.navigateWithQuery('settings', { tab: 'mcp' }),
            [CHAT_ACTIONS.GOTO_MODELS_DOWNLOAD]: () => host.navigation.navigateWithQuery('models', { action: MODELS_ACTION_DOWNLOAD_MODEL }),
            [CHAT_ACTIONS.RESTORE_PARAMETER_DEFAULTS]: () => host.execution.run('chat:restoreParameterDefaultsAction', () => host.configuration.restoreDefaults())
        }),
        [CHAT_ACTIONS.REFRESH_MEMORY]: () => host.execution.run('chat:refreshMemory', () => host.configuration.refreshMemory()),
        [CHAT_ACTIONS.REFRESH_PRESETS]: () => host.configuration.refreshPresets(),
        [CHAT_ACTIONS.RESET_PRESETS]: () => host.configuration.resetPresets(),
        [CHAT_ACTIONS.NEW_PRESET]: () => host.configuration.newPreset(),
        [CHAT_ACTIONS.APPLY_PRESET]: (actionElement) => host.configuration.applyPreset(actionElement),
        [CHAT_ACTIONS.REPLACE_PRESET]: (actionElement) => host.configuration.replacePreset(actionElement),
        [CHAT_ACTIONS.RENAME_PRESET]: (actionElement) => host.configuration.renamePreset(actionElement),
        [CHAT_ACTIONS.REMOVE_PRESET]: (actionElement) => host.configuration.removePreset(actionElement),
        [CHAT_ACTIONS.SUBMIT_PRESET_EDITOR]: () => host.configuration.submitPresetEditor(),
        [CHAT_ACTIONS.CANCEL_PRESET_EDITOR]: () => host.configuration.cancelPresetEditor(),
        [CHAT_ACTIONS.REVIEW_PRESET_EDITOR]: () => host.configuration.reviewPresetEditor(),
        [CHAT_ACTIONS.GOTO_MODEL_SETTINGS]: createModelNavigationHandler(host, () => host.conversation.currentModel(), { query: { tab: 'parameters' }, defaultPage: 'models' }),
        [CHAT_ACTIONS.OPEN_MODEL_DETAIL]: createModelNavigationHandler(host, (actionElement) => {
            return actionElement ? host.presentation.actionData(actionElement, 'model-id') : null;
        })
    };
};

export { createChatShellActionHandlers };
