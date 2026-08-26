/* SoAI - Model detail page control layer guards [frontend/assets/ts/pages/modeldetail/controllers/page/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_MANAGE_VIRTUAL_MODELS } from '@core/models/pageActions.ts';
import { resolveTabFromQuery } from '@core/queryTabs.ts';
import { IN_PLACE_SEARCH_DEBOUNCE_MS } from '@core/search/searchDebounce.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ModelDetailSetupDependencies extends PageLayoutOwnerHost, PageResourcesOwnerHost {
    loadIcons: () => Promise<void>;
    setupHeaderButtons: () => void;
    notifySaveChanged: () => void;
    parameterView: { setSearchFilter: (query: string) => void; clearSearchFilter: () => void };
    router: { getQueryParameters: () => Record<string, string> };
    initializeTabsComponent: () => Promise<void>;
    onTabChange: (tabId: string) => void;
}

interface ModelDetailLoadDependencies {
    loadModelDetails: () => Promise<void>;
    testModalManager: { openTestModal: () => void };
}

interface ModelDetailSwitchToParametersDependencies extends PageLayoutOwnerHost {
    isVirtualModel: () => boolean;
    router: { navigateWithQuery?: (page: string, query: Record<string, string>) => void } | null;
}

interface ModelDetailDestroyDependencies {
    parameterView: { dispose: () => void };
    testModalManager: { teardownLogStream: () => void };
}

const setupModelDetailPage = async (session: ModelDetailSession, host: ModelDetailSetupDependencies): Promise<void> => {
    await host.loadIcons();
    host.setupHeaderButtons();
    host.notifySaveChanged();
    host.layout.createSearch('modelDetail-search-container', {
        placeholder: i18n.t('modelDetail.searchPlaceholder'),
        debounceTime: IN_PLACE_SEARCH_DEBOUNCE_MS,
        onSearch: (query: string) => host.parameterView.setSearchFilter(query),
        onClear: () => host.parameterView.clearSearchFilter()
    });
    const queryParameters = host.router.getQueryParameters();
    const queryTab = resolveTabFromQuery(queryParameters, ['overview', 'parameters']);
    if (queryTab) {
        session.activeTab = queryTab;
    }
    const pendingAction = queryParameters['action'];
    if (pendingAction) {
        session.pendingAction = pendingAction;
    }
    await host.initializeTabsComponent();
    host.onTabChange(session.activeTab);
};

const loadModelDetailDataAndPendingAction = async (session: ModelDetailSession, host: ModelDetailLoadDependencies): Promise<void> => {
    await host.loadModelDetails();
    if (session.pendingAction !== 'test') {
        return;
    }
    session.pendingAction = null;
    if (session.loadError || !session.model) {
        return;
    }
    host.testModalManager.openTestModal();
};

const handleModelDetailSwitchToParametersAction = (session: ModelDetailSession, host: ModelDetailSwitchToParametersDependencies): void => {
    if (host.isVirtualModel()) {
        if (!host.router?.navigateWithQuery) {
            throw new Error('ModelDetailPage requires router.navigateWithQuery for virtual model navigation');
        }
        const virtualModelCandidate = session.model?.name ?? session.model?.id;
        if (!isString(virtualModelCandidate) || !virtualModelCandidate.trim()) {
            throw new Error('ModelDetailPage virtual model navigation requires a model name or id');
        }
        host.router.navigateWithQuery('models', { action: MODELS_ACTION_MANAGE_VIRTUAL_MODELS, vm: virtualModelCandidate });
        return;
    }
    const tabsComponent = host.layout.getTabs();
    if (!tabsComponent) {
        throw new Error('ModelDetailPage requires tabs component for parameter switching');
    }
    tabsComponent.setActiveTab('parameters');
};

const cleanupModelDetailPage = (session: ModelDetailSession, host: ModelDetailDestroyDependencies): void => {
    session.listeners?.abort();
    session.listeners = null;
    session.ui = null;
    session.deletionStream?.cancel?.();
    session.deletionStream = null;
    if (session.modelSubscription) {
        if (isFunction(session.modelSubscription.unsubscribe)) {
            session.modelSubscription.unsubscribe();
        } else {
            session.modelSubscription.close?.();
        }
    }
    session.modelSubscription = null;
    session.backendDocumentationUrl = null;
    host.parameterView.dispose();
    host.testModalManager.teardownLogStream();
};

const ensureModelDetailUi = <UiValue>(session: { ui: UiValue | null }, pageDom: PageDomOwnerHost['pageDom'], createUi: (resolvers: { requireHTMLElement: (selector: string, context?: ParentNode) => HTMLElement; optionalHTMLElement: (selector: string, context?: ParentNode) => HTMLElement | null }) => UiValue): UiValue => {
    if (session.ui) {
        return session.ui;
    }
    session.ui = createUi({
        requireHTMLElement: (selector: string, context?: ParentNode) => {
            if (context && context instanceof Element) {
                return pageDom.requireHTMLElement(selector, context);
            }
            return pageDom.requireHTMLElement(selector);
        },
        optionalHTMLElement: (selector: string, context?: ParentNode) => {
            if (context && context instanceof Element) {
                return pageDom.optionalHTMLElement(selector, context);
            }
            return pageDom.optionalHTMLElement(selector);
        }
    });
    return session.ui;
};

export { cleanupModelDetailPage, ensureModelDetailUi, handleModelDetailSwitchToParametersAction, loadModelDetailDataAndPendingAction, setupModelDetailPage };
export type { ModelDetailDestroyDependencies, ModelDetailLoadDependencies, ModelDetailSetupDependencies, ModelDetailSwitchToParametersDependencies };
