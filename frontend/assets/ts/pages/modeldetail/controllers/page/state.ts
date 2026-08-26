/* SoAI - Model detail page control layer state [frontend/assets/ts/pages/modeldetail/controllers/page/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveModelPluginName } from '@core/models/modelIdentity.ts';
import { applyPageHeaderTitleDisplay } from '@core/routing/pages/basepagelayout/pageHeaderTitle.ts';
import { isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { extractCleanModelIdentifier } from '@pages/modeldetail/formatting/modelDetailFormatting.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ModelDetailStateHost extends PageDomOwnerHost {
    model: ModelRecord | null;
    pluginCollectionSnapshot: JsonValue[];
    getModelDisplayName: () => string;
    getModelSourceModelId: () => string | undefined;
}

const setModelDetailInfo = (host: PageDomOwnerHost, id: string, value: JsonValue | null | undefined, format: (input: JsonValue | null | undefined) => string | null = (input: JsonValue | null | undefined) => (isNullOrUndefined(input) || input === '' ? null : String(input))): void => {
    const element = host.pageDom.optional(id);
    const item = element?.closest('.info-item, .model-description-section, .stat-row, .modeldetail-info-row, .modeldetail-metrics-row');
    const formatted = format(value);
    const hasValue = isString(formatted) && formatted.length > 0;
    if (item) {
        host.pageDom.toggleClass(item, 'u-hidden', !hasValue);
    }
    if (hasValue && element) {
        host.pageDom.updateText(element, formatted);
    }
};

const getModelDetailPluginStatus = (model: ModelRecord | null): string | null => {
    return model?.pluginStatus ?? model?.state ?? model?.status ?? model?.newState ?? null;
};

const getModelDetailDisplayName = (model: ModelRecord | null): string => {
    return model?.alias ?? model?.displayName ?? model?.name ?? model?.id ?? model?.sourceModelId ?? model?.modelId ?? '';
};

const getModelDetailSourceModelId = (model: ModelRecord | null): string | undefined => {
    return model?.sourceModelId;
};

const getModelDetailPluginName = (model: ModelRecord | null): string => {
    return model ? resolveModelPluginName(model) : '';
};

const findModelDetailPluginRecord = (host: Pick<ModelDetailStateHost, 'pluginCollectionSnapshot'>, pluginName: string, plugins: JsonValue[] | null = null): PluginRecord | null => {
    const key = pluginName.trim().toLowerCase();
    if (!key) {
        return null;
    }
    const list = plugins ?? host.pluginCollectionSnapshot;
    const match = list.find((entry: JsonValue) => {
        if (!isObject(entry)) {
            return false;
        }
        const name = entry['name'];
        return isString(name) && name.toLowerCase() === key;
    });
    if (!match) {
        return null;
    }
    if (!isObject(match)) {
        throw new TypeError('Plugin collection entry must be an object');
    }
    return match;
};

const updateModelDetailHeaderTitle = (host: ModelDetailStateHost): void => {
    const titleElement = host.pageDom.optionalHTMLElement('.page-header-title');
    if (!titleElement || !host.model) {
        return;
    }
    const displayName = host.getModelDisplayName();
    const hasAlias = host.model.hasAlias ?? (host.model.alias || host.model.displayName);
    applyPageHeaderTitleDisplay(titleElement, hasAlias ? displayName : extractCleanModelIdentifier(host.getModelSourceModelId()) || displayName);
};

const updateModelDetailHeaderDescription = (host: ModelDetailStateHost): void => {
    const descriptionElement = host.pageDom.optionalHTMLElement('.page-header-description');
    if (!descriptionElement || !host.model) {
        return;
    }
    host.pageDom.updateText(descriptionElement, host.model.universalId || host.model.id || host.model.name || '');
};

const updateModelDetailHeaderInfo = (host: ModelDetailStateHost): void => {
    updateModelDetailHeaderTitle(host);
    updateModelDetailHeaderDescription(host);
};

export { findModelDetailPluginRecord, getModelDetailDisplayName, getModelDetailPluginName, getModelDetailPluginStatus, getModelDetailSourceModelId, setModelDetailInfo, updateModelDetailHeaderDescription, updateModelDetailHeaderInfo, updateModelDetailHeaderTitle };
export type { ModelDetailStateHost };
