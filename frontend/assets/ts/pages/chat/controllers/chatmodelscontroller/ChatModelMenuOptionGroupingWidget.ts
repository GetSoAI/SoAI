/* SoAI - Shared provider grouping and status labeling for chat model selection menus [frontend/assets/ts/pages/chat/controllers/chatmodelscontroller/ChatModelMenuOptionGroupingWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { capitalize } from '@core/primitives/text.ts';
import { isString } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';

export type ChatModelProviderGroup = {
    label: string;
    models: ModelData[];
};

export const resolveChatModelProviderKey = (model: ModelData): string => {
    const providerValue = model.provider;
    const provider = isString(providerValue) && providerValue.trim() ? providerValue.trim() : 'default';
    return provider.toLowerCase();
};

export const groupChatModelsByProvider = (models: ModelData[]): Map<string, ChatModelProviderGroup> => {
    const byProvider = new Map<string, ChatModelProviderGroup>();
    for (const model of models) {
        const key = resolveChatModelProviderKey(model);
        const existing = byProvider.get(key);
        if (existing) {
            existing.models.push(model);
            continue;
        }
        byProvider.set(key, { label: capitalize(key), models: [model] });
    }
    return byProvider;
};

export const resolveChatModelStatusSuffix = (model: ModelData): string => {
    if (model.loaded) {
        return i18n.t('chat.models.loaded');
    }
    if (model.available) {
        return i18n.t('chat.models.available');
    }
    return '';
};
