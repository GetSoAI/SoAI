/* SoAI - Shared chat parameter editor state [frontend/assets/ts/core/chat/parameters/parameterEditorState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneChatParameters, type ChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';

type ChatParameterEditorPrompts = {
    userSystemPrompt: string | null;
    userSystemPromptLockEnabled: boolean;
    soaiSystemPromptEnabled: boolean;
};

type ChatParameterEditorState = {
    parameters: ChatParameters;
    prompts: ChatParameterEditorPrompts;
};

const cloneChatParameterEditorState = (state: ChatParameterEditorState): ChatParameterEditorState => ({
    parameters: cloneChatParameters(state.parameters),
    prompts: {
        userSystemPrompt: state.prompts.userSystemPrompt,
        userSystemPromptLockEnabled: state.prompts.userSystemPromptLockEnabled,
        soaiSystemPromptEnabled: state.prompts.soaiSystemPromptEnabled
    }
});

const createChatParameterEditorProjection = (state: ChatParameterEditorState): string => JSON.stringify(state);

export { cloneChatParameterEditorState, createChatParameterEditorProjection };
export type { ChatParameterEditorPrompts, ChatParameterEditorState };
