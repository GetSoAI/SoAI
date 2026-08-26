/* SoAI - Chat feature form runtime [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/service/formRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import { readRagConfigFromForm } from '@features/chat/conversationsettings/ragconversationsettings/state.ts';
import type { RagConversationSettingsViewBindings } from '@features/chat/conversationsettings/ragconversationsettings/service/viewBindings.ts';

const readRagFormValues = (view: RagConversationSettingsViewBindings, baselineConfig: RagConfig | null): RagConfig | null => {
    return readRagConfigFromForm({
        baselineConfig,
        requireInput: (selector) => view.requireInput(selector),
        requireSelect: (selector) => view.requireSelect(selector)
    });
};

export { readRagFormValues };
