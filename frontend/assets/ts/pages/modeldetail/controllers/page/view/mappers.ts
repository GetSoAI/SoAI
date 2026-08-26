/* SoAI - Model detail page control layer view mapping [frontend/assets/ts/pages/modeldetail/controllers/page/view/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { resolveOpenAIModalityDescriptor, resolveOpenAITokenDescriptor } from '@features/catalog/public.ts';
import type { OpenAICapabilityOverrideCategory } from '@features/models/public.ts';
import { findModelDetailPluginRecord, getModelDetailDisplayName, getModelDetailPluginName, getModelDetailPluginStatus, getModelDetailSourceModelId, setModelDetailInfo, updateModelDetailHeaderInfo } from '@pages/modeldetail/controllers/page/state.ts';
import type { ModelDetailSharedUiHost, ModelDetailViewDependencies, ModelDetailViewHost } from '@pages/modeldetail/controllers/page/view/types.ts';
import type { ModelDetailCardSectionsHost } from '@pages/modeldetail/rendering/modelDetailCardSections.ts';
import type { ModelDetailModelInfoHost } from '@pages/modeldetail/rendering/modelDetailModelInfoSection.ts';

interface ModelDetailModelInfoCallbacks {
    updateBackendDocButtonVisibility: () => void;
    populateDetailCards: () => void;
}

const composeModelDetailView = (host: ModelDetailViewDependencies): ModelDetailViewHost => {
    const getModelDisplayName = (): string => getModelDetailDisplayName(host.session.model);
    const getModelSourceModelId = (): string | undefined => getModelDetailSourceModelId(host.session.model);
    const getModelPluginName = (): string => getModelDetailPluginName(host.session.model);
    const getPluginStatus = (): string | null => getModelDetailPluginStatus(host.session.model);
    const resolveOpenAICapabilityLabel = (category: OpenAICapabilityOverrideCategory, token: string): string => {
        if (category === 'modalities') {
            return resolveOpenAIModalityDescriptor(token).label;
        }
        return resolveOpenAITokenDescriptor(category, token).label;
    };
    const createStateHost = (): {
        pageDom: ModelDetailViewDependencies['pageDom'];
        model: ModelRecord | null;
        pluginCollectionSnapshot: JsonValue[];
        getModelDisplayName: () => string;
        getModelSourceModelId: () => string | undefined;
    } => ({
        pageDom: host.pageDom,
        model: host.session.model,
        pluginCollectionSnapshot: host.session.pluginSnapshot,
        getModelDisplayName,
        getModelSourceModelId
    });

    return {
        state: {
            pageDom: host.pageDom,
            get model() {
                return host.session.model;
            },
            get pluginCollectionSnapshot() {
                return host.session.pluginSnapshot;
            },
            get backendDocumentationUrl() {
                return host.session.backendDocumentationUrl;
            },
            parameterState: host.parameterState,
            get activeTab() {
                return host.session.activeTab;
            },
            streamManager: host.streamManager,
            ensureUi: () => host.ensureUi(),
            isVirtualModel: () => host.isVirtualModel()
        },
        presentation: {
            sanitizeText: (value: JsonValue | null | undefined) => host.services.sanitizeText(value === null || value === undefined ? value : String(value)),
            sanitizeClassName: (value: string, fallback: string) => host.services.sanitizeClassName(value, fallback),
            sanitizeAttribute: (value: string) => host.sanitizeAttribute(value),
            setInfo: (id: string, value: JsonValue | null | undefined, formatter?: (value: JsonValue | null | undefined) => string | null): void => {
                setModelDetailInfo(createStateHost(), id, value, formatter);
            },
            getModelPluginName,
            findPluginRecord: (pluginName: string): PluginRecord | null =>
                findModelDetailPluginRecord(
                    {
                        pluginCollectionSnapshot: host.session.pluginSnapshot
                    },
                    pluginName
                ),
            getModelDisplayName,
            getPluginStatus,
            describePluginStatus: (value: string): string => host.statusManager?.getDescription(value) ?? value,
            updateHeaderInfo: (): void => {
                updateModelDetailHeaderInfo(createStateHost());
            }
        },
        actions: {
            getManageAliasButton: (): HTMLElement | null => host.ensureUi().manageAliasButton,
            getStopPluginButton: (): HTMLElement | null => host.ensureUi().stopPluginButton,
            getModelSourceModelId,
            setUiValue: (element: Element, value: string, options?: { attribute?: string }): void => {
                host.pageElements.setValue(element, value, options);
            },
            modalPresenter: host.modalPresenter,
            getOpenAICapabilityState: () => host.getOpenAICapabilityState(),
            resolveOpenAICapabilityLabel
        }
    };
};

const createModelDetailSharedUiHost = (host: ModelDetailViewHost): ModelDetailSharedUiHost => {
    return {
        pageDom: host.state.pageDom,
        sanitizeText: (value: JsonValue | null | undefined): string => host.presentation.sanitizeText(value === null || value === undefined ? value : String(value))
    };
};

const createModelDetailCardSectionsHost = (host: ModelDetailViewHost): ModelDetailCardSectionsHost => {
    const sharedUiHost = createModelDetailSharedUiHost(host);
    return {
        pageDom: host.state.pageDom,
        model: host.state.model,
        isVirtualModel: (): boolean => host.state.isVirtualModel(),
        parameterState: host.state.parameterState,
        sanitizeText: sharedUiHost.sanitizeText,
        sanitizeClassName: (value: string, fallback: string): string => host.presentation.sanitizeClassName(value, fallback),
        setInfo: (id: string, value: JsonValue | null | undefined, formatter?: (value: JsonValue | null | undefined) => string | null): void => host.presentation.setInfo(id, value, formatter),
        getModelPluginName: (): string => host.presentation.getModelPluginName(),
        findPluginRecord: (pluginName: string): PluginRecord | null => host.presentation.findPluginRecord(pluginName),
        getDeleteModelButton: (): HTMLButtonElement => host.state.ensureUi().deleteModelButton,
        getOpenAICapabilityState: () => host.actions.getOpenAICapabilityState(),
        resolveOpenAICapabilityLabel: (category, token) => host.actions.resolveOpenAICapabilityLabel(category, token)
    };
};

const createModelDetailModelInfoHost = (host: ModelDetailViewHost, callbacks: ModelDetailModelInfoCallbacks): ModelDetailModelInfoHost => {
    if (!host.state.model) {
        throw new Error('ModelDetailPage model info host requires a loaded model');
    }
    const sharedUiHost = createModelDetailSharedUiHost(host);
    return {
        pageDom: host.state.pageDom,
        model: host.state.model,
        getModelDisplayName: (): string => host.presentation.getModelDisplayName(),
        isVirtualModel: (): boolean => host.state.isVirtualModel(),
        getPluginStatus: (): string | null => host.presentation.getPluginStatus(),
        describePluginStatus: (value: string): string => host.presentation.describePluginStatus(value),
        setInfo: (id: string, value: JsonValue | null | undefined, formatter?: (value: JsonValue | null | undefined) => string | null): void => host.presentation.setInfo(id, value, formatter),
        sanitizeAttribute: (value: string): string => host.presentation.sanitizeAttribute(value),
        sanitizeText: sharedUiHost.sanitizeText,
        getStopPluginButton: (): HTMLElement | null => host.actions.getStopPluginButton(),
        getManageAliasButton: (): HTMLElement | null => host.actions.getManageAliasButton(),
        updateBackendDocButtonVisibility: callbacks.updateBackendDocButtonVisibility,
        populateDetailCards: callbacks.populateDetailCards,
        updateHeaderInfo: (): void => host.presentation.updateHeaderInfo()
    };
};

export { composeModelDetailView, createModelDetailCardSectionsHost, createModelDetailModelInfoHost, createModelDetailSharedUiHost };
export type { ModelDetailModelInfoCallbacks };
