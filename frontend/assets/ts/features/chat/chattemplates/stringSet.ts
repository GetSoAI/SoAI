/* SoAI - Chat feature string set [frontend/assets/ts/features/chat/chattemplates/stringSet.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { ChatTemplateStringSet } from '@features/chat/chattemplates/stringSetTypes.ts';
import { resolveBasicsTemplateStrings } from '@features/chat/chattemplates/chatStringsBasics.ts';
import { resolveConfigurationModelParametersTemplateStrings } from '@features/chat/chattemplates/chatStringsConfigurationModelParameters.ts';
import { resolveConfigurationUiTemplateStrings } from '@features/chat/chattemplates/chatStringsConfigurationUi.ts';
import { resolveInputActionsVoiceTemplateStrings } from '@features/chat/chattemplates/chatStringsInputActionsVoice.ts';
import { resolveKnowledgeMcpAgentTemplateStrings } from '@features/chat/chattemplates/chatStringsKnowledgeMcpAgent.ts';

const resolveTemplateStrings = (sanitizer: SanitizerApi): ChatTemplateStringSet => {
    return {
        ...resolveBasicsTemplateStrings(sanitizer),
        ...resolveConfigurationUiTemplateStrings(sanitizer),
        ...resolveConfigurationModelParametersTemplateStrings(sanitizer),
        ...resolveInputActionsVoiceTemplateStrings(sanitizer),
        ...resolveKnowledgeMcpAgentTemplateStrings(sanitizer)
    };
};

export { resolveTemplateStrings };
