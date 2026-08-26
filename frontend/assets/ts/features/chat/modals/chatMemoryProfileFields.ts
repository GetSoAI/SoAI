/* SoAI - Chat feature memory profile fields [frontend/assets/ts/features/chat/modals/chatMemoryProfileFields.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAllowedStringValue } from '@core/types/payloadValueReaders.ts';
import type { ChatMemoryProfile, ChatMemoryProfileUpdateRequest } from '@core/api/contracts/webuiMemoryContracts.ts';

type ChatMemoryProfileFieldName = 'preferred_name' | 'assistant_name' | 'role_background' | 'current_goals' | 'preferences' | 'dislikes_to_avoid' | 'communication_style' | 'recurring_tools_projects' | 'extra_notes';
type ChatMemoryProfileFieldInputType = 'text' | 'textarea';

interface ChatMemoryProfileFieldDefinition {
    name: ChatMemoryProfileFieldName;
    uiToken: string;
    inputType: ChatMemoryProfileFieldInputType;
    maxLength: number | null;
    rows: number | null;
}

const CHAT_MEMORY_PROFILE_FIELD_NAMES: readonly ChatMemoryProfileFieldName[] = Object.freeze(['preferred_name', 'assistant_name', 'role_background', 'current_goals', 'preferences', 'dislikes_to_avoid', 'communication_style', 'recurring_tools_projects', 'extra_notes']);

const isChatMemoryProfileFieldName = (value: string | null | undefined): value is ChatMemoryProfileFieldName => isAllowedStringValue(value, CHAT_MEMORY_PROFILE_FIELD_NAMES);

const resolveChatMemoryProfileFieldDefinition = (fieldName: string): ChatMemoryProfileFieldDefinition => {
    if (!isChatMemoryProfileFieldName(fieldName)) {
        throw new Error(`Unsupported chat memory profile field: ${fieldName}`);
    }
    switch (fieldName) {
        case 'preferred_name':
            return { name: fieldName, uiToken: 'preferred-name', inputType: 'text', maxLength: 50, rows: null };
        case 'assistant_name':
            return { name: fieldName, uiToken: 'assistant-name', inputType: 'text', maxLength: 50, rows: null };
        case 'role_background':
            return { name: fieldName, uiToken: 'role-background', inputType: 'textarea', maxLength: null, rows: 3 };
        case 'current_goals':
            return { name: fieldName, uiToken: 'current-goals', inputType: 'textarea', maxLength: null, rows: 3 };
        case 'preferences':
            return { name: fieldName, uiToken: 'preferences', inputType: 'textarea', maxLength: null, rows: 3 };
        case 'dislikes_to_avoid':
            return { name: fieldName, uiToken: 'dislikes-to-avoid', inputType: 'textarea', maxLength: null, rows: 3 };
        case 'communication_style':
            return { name: fieldName, uiToken: 'communication-style', inputType: 'textarea', maxLength: null, rows: 3 };
        case 'recurring_tools_projects':
            return { name: fieldName, uiToken: 'recurring-tools-projects', inputType: 'textarea', maxLength: null, rows: 3 };
        case 'extra_notes':
            return { name: fieldName, uiToken: 'extra-notes', inputType: 'textarea', maxLength: null, rows: 3 };
    }
};

const readChatMemoryProfileFieldValue = (profile: ChatMemoryProfile, fieldName: ChatMemoryProfileFieldName): string => {
    switch (fieldName) {
        case 'preferred_name':
            return profile.preferredName ?? '';
        case 'assistant_name':
            return profile.assistantName ?? '';
        case 'role_background':
            return profile.roleBackground ?? '';
        case 'current_goals':
            return profile.currentGoals ?? '';
        case 'preferences':
            return profile.preferences ?? '';
        case 'dislikes_to_avoid':
            return profile.dislikesToAvoid ?? '';
        case 'communication_style':
            return profile.communicationStyle ?? '';
        case 'recurring_tools_projects':
            return profile.recurringToolsProjects ?? '';
        case 'extra_notes':
            return profile.extraNotes ?? '';
    }
};

const writeChatMemoryProfileFieldValue = (profile: ChatMemoryProfileUpdateRequest, fieldName: ChatMemoryProfileFieldName, value: string): void => {
    switch (fieldName) {
        case 'preferred_name':
            profile.preferredName = value;
            return;
        case 'assistant_name':
            profile.assistantName = value;
            return;
        case 'role_background':
            profile.roleBackground = value;
            return;
        case 'current_goals':
            profile.currentGoals = value;
            return;
        case 'preferences':
            profile.preferences = value;
            return;
        case 'dislikes_to_avoid':
            profile.dislikesToAvoid = value;
            return;
        case 'communication_style':
            profile.communicationStyle = value;
            return;
        case 'recurring_tools_projects':
            profile.recurringToolsProjects = value;
            return;
        case 'extra_notes':
            profile.extraNotes = value;
            return;
    }
};

export { CHAT_MEMORY_PROFILE_FIELD_NAMES, isChatMemoryProfileFieldName, readChatMemoryProfileFieldValue, resolveChatMemoryProfileFieldDefinition, writeChatMemoryProfileFieldValue };
export type { ChatMemoryProfileFieldDefinition, ChatMemoryProfileFieldName };
