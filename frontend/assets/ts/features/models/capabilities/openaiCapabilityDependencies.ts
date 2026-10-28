/* SoAI - OpenAI capability prerequisite relationships [frontend/assets/ts/features/models/capabilities/openaiCapabilityDependencies.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { OpenAICapabilityOverrideCategory } from '@core/openai/capabilityCategories.ts';

interface OpenAICapabilityRequirement {
    category: OpenAICapabilityOverrideCategory;
    token: string;
    reason: string;
}

const resolveOpenAICapabilityRequirement = (category: OpenAICapabilityOverrideCategory, token: string): OpenAICapabilityRequirement | null => {
    if (category === 'responses_features') return { category: 'endpoints', token: 'responses', reason: i18n.t('modelDetail.cards.capabilities.lockedReasons.requiresResponses') };
    if (category === 'image_features') return { category: 'endpoints', token: 'images', reason: i18n.t('modelDetail.cards.capabilities.lockedReasons.requiresImages') };
    if (category === 'chat_features' && token === 'vision') return { category: 'modalities', token: 'vision', reason: i18n.t('modelDetail.cards.capabilities.lockedReasons.requiresVision') };
    if (category === 'chat_features' && token === 'input_audio') return { category: 'modalities', token: 'audio', reason: i18n.t('modelDetail.cards.capabilities.lockedReasons.requiresAudio') };
    return null;
};

export { resolveOpenAICapabilityRequirement };
export type { OpenAICapabilityRequirement };
