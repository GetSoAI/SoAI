/* SoAI - Chat model control menu option grouping and search indexing [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuOptionsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createSearchTextIndex } from '@core/search/searchQuery.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { groupChatModelsByProvider, resolveChatModelStatusSuffix } from '@pages/chat/controllers/chatmodelscontroller/ChatModelMenuOptionGroupingWidget.ts';

type ChatModelMenuOption = {
    id: string;
    label: string;
    searchIndex: string;
    disabled: boolean;
    selected: boolean;
};

type ChatModelMenuOptionGroup = {
    label: string;
    options: ChatModelMenuOption[];
};

const createModelSearchIndex = (model: ModelData, providerLabel: string): string => {
    return createSearchTextIndex([model.id, model.name, model.universalId, model.modelId, model.sourceModelId, model.rawUpstreamModelId, model.alias, model.displayName, model.plugin, model.pluginName, model.provider, model.providerId, model.providerName, providerLabel].filter((value): value is string => typeof value === 'string'));
};

const createModelOption = (model: ModelData, selectedModelId: string | null, providerLabel: string): ChatModelMenuOption => {
    const statusSuffix = resolveChatModelStatusSuffix(model);
    const label = `${model.name} ${statusSuffix}`.trim();
    const selected = selectedModelId !== null && model.id === selectedModelId;
    const disabled = !isChatSelectableModel(model);
    return {
        id: model.id,
        label,
        searchIndex: createModelSearchIndex(model, providerLabel),
        disabled,
        selected
    };
};

const buildChatModelMenuOptionGroups = (inputArguments: { models: ModelData[]; selectedModelId: string | null }): ChatModelMenuOptionGroup[] => {
    const groupsByProvider = groupChatModelsByProvider(inputArguments.models);
    const providers = Array.from(groupsByProvider.values());
    const shouldGroup = providers.length > 1;

    if (!shouldGroup) {
        const singleProvider = providers[0] ?? null;
        const models = singleProvider?.models ?? inputArguments.models;
        const providerLabel = singleProvider?.label ?? '';
        return [{ label: '', options: models.map((model) => createModelOption(model, inputArguments.selectedModelId, providerLabel)) }];
    }

    const locale = getCurrentLocale();
    return providers.map((provider) => ({ label: provider.label, options: provider.models.map((model) => createModelOption(model, inputArguments.selectedModelId, provider.label)) })).sort((left, right) => left.label.localeCompare(right.label, locale));
};

export { buildChatModelMenuOptionGroups };
export type { ChatModelMenuOption, ChatModelMenuOptionGroup };
