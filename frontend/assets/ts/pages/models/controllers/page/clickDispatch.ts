/* SoAI - Models page click dispatch [frontend/assets/ts/pages/models/controllers/page/clickDispatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createCardActionDispatcher } from '@core/dom/cardActionDispatcher.ts';
import { hasDataActionElement, shouldPreventDefaultForDelegatedActionElement } from '@core/dom/dataAction.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DOWNLOAD_MODEL, MODELS_ACTION_MANAGE_PROVIDERS, MODELS_ACTION_MANAGE_VIRTUAL_MODELS, MODELS_ACTION_METRIC_BADGE, MODELS_ACTION_OPEN_METRICS, MODELS_ACTION_OPEN_PROVIDER_TAB } from '@core/models/pageActions.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isActionToggleInteractionDisabled } from '@core/toggleSwitch.ts';
import { hasOwn, isNullOrUndefined } from '@core/typeGuards.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { MODELS_ACTION_SORT_LIST, MODELS_ACTION_TOGGLE_ENABLED, MODELS_ACTION_TOGGLE_VIEW_MODE, isModelsActionId, isModelsPageActionId, type ModelsActionId, type ModelsDataActionId } from '@pages/models/actions.ts';
import { MODEL_ACTION_HANDLERS, type ModelsActionHost } from '@pages/models/contracts/ModelPageSupport.ts';
import { isModelRecord } from '@pages/models/controllers/modelsModelProperties.ts';

type InitialActionContext = { action: string; plugin?: string; vm?: string };
interface ModelsActionClickDependencies {
    cardSelector: string;
    getModelsActionHost: () => ModelsActionHost;
    getItemFromCard: (card: Element) => ResourceIncomingValue | null | undefined;
    openDownloadModelModal: () => void;
    openAddProviderTab: () => void;
    openProviderTab: (event: Event) => void;
    navigateToMetrics: () => void;
    openVirtualModelsModal: () => void;
    openProvidersModal: () => Promise<void>;
    toggleViewMode: () => void;
    sortList: (actionElement: HTMLElement) => void;
    handleMetricBadgeNavigation: (badge: Element, model: ModelRecord) => boolean;
    logInvalidActionModel: (action: string, model: ResourceIncomingValue | null | undefined) => void;
    handleActionError: (error: Error) => void;
}

const isKnownModelAction = (value: string): value is keyof typeof MODEL_ACTION_HANDLERS => {
    return hasOwn(MODEL_ACTION_HANDLERS, value);
};

const consumeInitialActionContext = (context: InitialActionContext | null): InitialActionContext | null => {
    if (!context) {
        return null;
    }
    return { ...context };
};

const requireActionHTMLElement = (actionElement: Element): HTMLElement => {
    if (!(actionElement instanceof HTMLElement) || !hasDataActionElement(actionElement)) {
        throw new Error('Models action dispatch requires an HTMLElement with data-action');
    }
    return actionElement;
};

const isDisabledModelToggleAction = (action: string, actionElement: Element): boolean => {
    return action === MODELS_ACTION_TOGGLE_ENABLED && isActionToggleInteractionDisabled(actionElement);
};

const handleMetricBadgeActionClick = (event: Event, actionElement: HTMLElement, dependencies: ModelsActionClickDependencies): boolean => {
    const dispatch = createCardActionDispatcher<typeof MODELS_ACTION_METRIC_BADGE, ModelRecord>({
        cardSelector: dependencies.cardSelector,
        context: 'Models metric badge action',
        resolveItem: (card): ModelRecord | null => {
            const item = dependencies.getItemFromCard(card);
            if (!isModelRecord(item)) {
                dependencies.logInvalidActionModel(MODELS_ACTION_METRIC_BADGE, item);
                return null;
            }
            return item;
        },
        onAction: ({ actionElement: metricElement, item }): void => {
            event.preventDefault();
            event.stopPropagation();
            dependencies.handleMetricBadgeNavigation(metricElement, item);
        }
    });
    dispatch({ event, action: MODELS_ACTION_METRIC_BADGE, actionElement });
    return true;
};

const handlePageActionClick = (event: Event, action: ModelsDataActionId, actionElement: HTMLElement, dependencies: ModelsActionClickDependencies): boolean => {
    if (!isModelsPageActionId(action)) {
        return false;
    }
    if (action === MODELS_ACTION_TOGGLE_VIEW_MODE) {
        event.preventDefault();
        event.stopPropagation();
        dependencies.toggleViewMode();
        return true;
    }
    if (action === MODELS_ACTION_SORT_LIST) {
        event.preventDefault();
        event.stopPropagation();
        dependencies.sortList(actionElement);
        return true;
    }
    if (action === MODELS_ACTION_METRIC_BADGE) {
        return handleMetricBadgeActionClick(event, actionElement, dependencies);
    }
    if (action === MODELS_ACTION_DOWNLOAD_MODEL) {
        event.preventDefault();
        event.stopPropagation();
        dependencies.openDownloadModelModal();
        return true;
    }
    if (action === MODELS_ACTION_MANAGE_VIRTUAL_MODELS) {
        event.preventDefault();
        event.stopPropagation();
        dependencies.openVirtualModelsModal();
        return true;
    }
    if (action === MODELS_ACTION_MANAGE_PROVIDERS) {
        event.preventDefault();
        event.stopPropagation();
        terminateHandledPromise(dependencies.openProvidersModal().catch(dependencies.handleActionError));
        return true;
    }
    if (action === MODELS_ACTION_ADD_PROVIDER) {
        event.preventDefault();
        event.stopPropagation();
        dependencies.openAddProviderTab();
        return true;
    }
    if (action === MODELS_ACTION_OPEN_PROVIDER_TAB) {
        event.preventDefault();
        event.stopPropagation();
        dependencies.openProviderTab(event);
        return true;
    }
    if (action === MODELS_ACTION_OPEN_METRICS) {
        event.preventDefault();
        event.stopPropagation();
        dependencies.navigateToMetrics();
        return true;
    }
    return false;
};

const handleModelActionClick = (event: Event, action: ModelsDataActionId, actionElement: Element, cardOverride: Element | null, modelOverride: ResourceIncomingValue | null | undefined, dependencies: ModelsActionClickDependencies): void => {
    const actionHtmlElement = requireActionHTMLElement(actionElement);
    if (!isModelsActionId(action) || !isKnownModelAction(action)) {
        return;
    }
    if (isDisabledModelToggleAction(action, actionHtmlElement)) {
        event.preventDefault();
        event.stopPropagation();
        return;
    }
    const dispatch = createCardActionDispatcher<ModelsActionId, ModelRecord>({
        cardSelector: dependencies.cardSelector,
        context: 'Models card action',
        resolveItem: (resolvedCard): ModelRecord | null => {
            const card = cardOverride ?? resolvedCard;
            const modelCandidate = isNullOrUndefined(modelOverride) ? dependencies.getItemFromCard(card) : modelOverride;
            if (!isModelRecord(modelCandidate)) {
                dependencies.logInvalidActionModel(action, modelCandidate);
                return null;
            }
            return modelCandidate;
        },
        onAction: ({ action: actionId, actionElement: resolvedActionElement, item }): void => {
            if (shouldPreventDefaultForDelegatedActionElement(resolvedActionElement)) {
                event.preventDefault();
            }
            event.stopPropagation();
            const result = MODEL_ACTION_HANDLERS[actionId](dependencies.getModelsActionHost(), item, event);
            terminateHandledPromise(Promise.resolve(result).catch(dependencies.handleActionError));
        }
    });
    dispatch({ event, action, actionElement: actionHtmlElement });
};

const createRootClickHandler = (dependencies: ModelsActionClickDependencies): ((event: Event, action: ModelsDataActionId, actionElementOverride?: HTMLElement | null) => void) => {
    return (event: Event, action: ModelsDataActionId, actionElementOverride?: HTMLElement | null): void => {
        try {
            if (!actionElementOverride) {
                return;
            }
            if (handlePageActionClick(event, action, actionElementOverride, dependencies)) {
                return;
            }
            handleModelActionClick(event, action, actionElementOverride, null, null, dependencies);
        } catch (error) {
            const runtimeError = ensureError(error);
            dependencies.handleActionError(runtimeError);
        }
    };
};

const navigateToModelDetail = (
    model: ModelRecord,
    options: { tab?: string; action?: string } | undefined,
    dependencies: {
        router: {
            navigate(path: string): Promise<void> | void;
            navigateWithQuery?: (path: string, query: Record<string, string>) => Promise<void> | void;
        };
        onInvalidModel: (model: ModelRecord) => void;
    }
): void => {
    const universalId = toTrimmedString(model?.universalId);
    if (!universalId) {
        dependencies.onInvalidModel(model);
        return;
    }
    const path = `model/${encodeSegment(universalId)}`;
    const query: Record<string, string> = {};
    if (options?.tab) {
        query['tab'] = options.tab;
    }
    if (options?.action) {
        query['action'] = options.action;
    }
    if (Object.keys(query).length > 0 && dependencies.router.navigateWithQuery) {
        void dependencies.router.navigateWithQuery(path, query);
    } else {
        void dependencies.router.navigate(path);
    }
};

export { consumeInitialActionContext, createRootClickHandler, handleModelActionClick, handlePageActionClick, navigateToModelDetail };
export type { InitialActionContext, ModelsActionClickDependencies };
