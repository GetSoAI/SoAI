/* SoAI - Model detail page control layer DOM contracts [frontend/assets/ts/pages/modeldetail/controllers/page/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
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

const PRESENCE_ATTRIBUTE = 'data-presence';

const resolveModelDetailParameterActions = (ui: ModelDetailUi): Element[] => [ui.resetAllParametersHeaderButton, ui.searchContainer];

const setupModelDetailHeaderButtons = (host: ModelDetailHeaderButtonsHost): void => {
    const ui = host.ensureUi();
    const saveParametersMarkup = uiHtml`${host.requireIconMarkup('SAVE')}<span>${i18n.t('modelDetail.buttons.saveParameters')}</span>`;
    const resetParametersMarkup = uiHtml`${host.requireIconMarkup('RESET')}<span>${i18n.t('modelDetail.buttons.resetAll')}</span>`;
    host.pageDom.updateHtml(ui.saveParametersHeaderButton, saveParametersMarkup);
    host.pageDom.updateHtml(ui.resetAllParametersHeaderButton, resetParametersMarkup);
    host.pageDom.updateHtml(ui.resetOverviewHeaderButton, resetParametersMarkup);
    host.pageDom.updateAttribute(ui.resetOverviewHeaderButton, 'data-presence-suspended', '');
    host.pageDom.updateAttribute(ui.resetAllParametersHeaderButton, 'data-presence-suspended', '');
    const testModelMarkup = uiHtml`${host.requireIconMarkup('TEST')}<span>${i18n.t('modelDetail.buttons.test')}</span>`;
    host.pageDom.updateHtml(ui.testModelHeaderButton, testModelMarkup);
    host.pageDom.updateAttribute(ui.searchContainer, PRESENCE_ATTRIBUTE, '');
};

const applyModelDetailTabChange = (session: ModelDetailSession, host: ModelDetailTabDependencies, newTab: string): void => {
    const ui = host.ensureUi();
    session.activeTab = newTab;
    [ui.overviewContent, ui.parametersContent].forEach((content: Element) => {
        host.pageDom.toggleClass(content, 'is-active', content.id === `${newTab}-content`);
    });
    const isParametersTab = newTab === 'parameters';
    host.pageDom.toggleClass(ui.resetOverviewHeaderButton, CSS_CLASSES.HIDDEN, isParametersTab);
    resolveModelDetailParameterActions(ui).forEach((element) => host.pageDom.toggleClass(element, CSS_CLASSES.HIDDEN, !isParametersTab));
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
