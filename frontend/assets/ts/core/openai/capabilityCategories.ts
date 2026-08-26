/* SoAI - Shared OpenAI capability categories [frontend/assets/ts/core/openai/capabilityCategories.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type OpenAICapabilityCategory = 'endpoints' | 'responses_features' | 'image_features' | 'chat_features';
type OpenAICategory = OpenAICapabilityCategory;
type OpenAICapabilityOverrideCategory = OpenAICapabilityCategory | 'modalities';

const OPENAI_CAPABILITY_CATEGORIES: readonly OpenAICapabilityCategory[] = Object.freeze(['endpoints', 'responses_features', 'image_features', 'chat_features']);
const OPENAI_CAPABILITY_OVERRIDE_CATEGORIES: readonly OpenAICapabilityOverrideCategory[] = Object.freeze([...OPENAI_CAPABILITY_CATEGORIES, 'modalities']);

const isOpenAICapabilityOverrideCategory = (value: string): value is OpenAICapabilityOverrideCategory => {
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        if (category === value) {
            return true;
        }
    }
    return false;
};

const isSafeOpenAICapabilityToken = (value: string): boolean => /^[a-z0-9_]+$/.test(value);

export { OPENAI_CAPABILITY_CATEGORIES, OPENAI_CAPABILITY_OVERRIDE_CATEGORIES, isOpenAICapabilityOverrideCategory, isSafeOpenAICapabilityToken };
export type { OpenAICapabilityOverrideCategory, OpenAICategory };
