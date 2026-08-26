/* SoAI - Model detail page control layer DOM contracts [frontend/assets/ts/pages/modeldetail/controllers/page/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { isString } from '@core/typeGuards.ts';
import type { ModelDetailUi } from '@pages/modeldetail/dom.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';

interface ModelDetailHeaderButtonsHost extends PageDomOwnerHost {
    ensureUi: () => ModelDetailUi;
    requireIconMarkup: (iconKey: string) => TrustedHtml;
}

interface ModelDetailTabDependencies extends PageDomOwnerHost {
    ensureUi: () => ModelDetailUi;
    renderParametersInterface: () => void;
    parameterView: {
        refreshModificationState: () => void;
    };
    updateBackendDocButtonVisibility: () => void;
}

interface ModelDetailLanguageChangedDependencies extends PageLayoutOwnerHost, PageResourcesOwnerHost {
    loadIcons: () => Promise<void>;
    setupHeaderButtons: () => void;
    initializeTabsComponent: () => Promise<void>;
    onTabChange: (tabId: string) => void;
    updateHeaderInfo: () => void;
    populateModelInfo: () => void;
    renderParametersInterface: () => void;
}

const setModelDetailElementVisibility = (host: ModelDetailTabDependencies, element: Element, visible: boolean): void => {
    host.pageDom.toggleClass(element, 'u-hidden', !visible);
    host.pageDom.updateStyle(element, 'display', visible ? '' : 'none');
    const filterShell = element.closest('.page-header-filter-select-shell');
    if (filterShell instanceof HTMLElement) {
        host.pageDom.toggleClass(filterShell, 'u-hidden', !visible);
        host.pageDom.updateStyle(filterShell, 'display', visible ? '' : 'none');
    }
};

const setupModelDetailHeaderButtons = (host: ModelDetailHeaderButtonsHost): void => {
    const ui = host.ensureUi();
    const saveParametersMarkup = uiHtml`${host.requireIconMarkup('SAVE')}<span>${i18n.t('modelDetail.buttons.saveParameters')}</span>`;
    const resetParametersMarkup = uiHtml`${host.requireIconMarkup('RESET')}<span>${i18n.t('modelDetail.buttons.resetAll')}</span>`;
    host.pageDom.updateHtml(ui.saveParametersHeaderButton, saveParametersMarkup);
    host.pageDom.updateHtml(ui.resetAllParametersHeaderButton, resetParametersMarkup);
    const testModelMarkup = uiHtml`${host.requireIconMarkup('TEST')}<span>${i18n.t('modelDetail.buttons.test')}</span>`;
    host.pageDom.updateHtml(ui.testModelHeaderButton, testModelMarkup);
};

const applyModelDetailTabChange = (session: ModelDetailSession, host: ModelDetailTabDependencies, newTab: string): void => {
    const ui = host.ensureUi();
    session.activeTab = newTab;
    [ui.overviewContent, ui.parametersContent].forEach((content: Element) => {
        host.pageDom.toggleClass(content, 'is-active', content.id === `${newTab}-content`);
    });
    const isParametersTab = newTab === 'parameters';
    [ui.saveParametersHeaderButton, ui.resetAllParametersHeaderButton, ui.searchContainer, ui.parameterUnifiedFilter].forEach((element) => setModelDetailElementVisibility(host, element, isParametersTab));
    if (isParametersTab) {
        if (!ui.parametersInterface.hasChildNodes()) {
            host.renderParametersInterface();
        } else {
            host.parameterView.refreshModificationState();
        }
    }
    host.updateBackendDocButtonVisibility();
};

const handleModelDetailLanguageChanged = async (session: ModelDetailSession, host: ModelDetailLanguageChangedDependencies): Promise<void> => {
    await host.loadIcons();
    host.setupHeaderButtons();
    const activeCandidate = session.activeTab;
    const tabsActive = host.layout.getTabs()?.activeTab;
    const nextTab = isString(activeCandidate) && activeCandidate ? activeCandidate : isString(tabsActive) ? tabsActive : 'overview';
    session.activeTab = nextTab;
    await host.initializeTabsComponent();
    host.layout.getTabs()?.setActiveTab(nextTab);
    host.onTabChange(nextTab);
    host.updateHeaderInfo();
    if (session.model) {
        host.populateModelInfo();
        host.renderParametersInterface();
    }
};

export { applyModelDetailTabChange, handleModelDetailLanguageChanged, setupModelDetailHeaderButtons };
export type { ModelDetailHeaderButtonsHost, ModelDetailLanguageChangedDependencies, ModelDetailTabDependencies };
