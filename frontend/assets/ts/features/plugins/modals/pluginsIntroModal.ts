/* SoAI - Plugins feature intro modal [frontend/assets/ts/features/plugins/modals/pluginsIntroModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { readFirstRunModalStateStatus, setFirstRunModalDismissed } from '@core/firstrun/state.ts';
import type { FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import { renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { renderStructuredTextSection, type StructuredTextSection } from '@core/richtextrenderer/structuredSections.ts';
import { uiHtml } from '@core/security/uiHtml.ts';

const PLUGINS_INTRO_MODAL_ID = 'plugins-intro-modal';

const createPluginsIntroSection = (): StructuredTextSection => ({
    id: 'plugins',
    getTitle: () => i18n.t('plugins.firstRun.title'),
    getHeading: () => i18n.t('plugins.firstRun.summary'),
    blocks: [
        {
            type: 'list',
            items: [() => i18n.t('plugins.firstRun.backendInstall'), () => i18n.t('plugins.firstRun.hardwareCompatibility'), () => i18n.t('plugins.firstRun.remotePlugins'), () => i18n.t('plugins.firstRun.pageGuide')]
        }
    ]
});

const createPluginsIntroModalElement = (): HTMLElement => {
    const modalId = PLUGINS_INTRO_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('plugins.firstRun.title'),
        description: i18n.t('common.modalDescriptions.pluginsIntro'),
        closeLabel: i18n.t('common.close')
    });
    const richText = renderStructuredTextSection(createPluginsIntroSection(), {
        idPrefix: `${modalId}-section-`,
        sectionClassName: 'first-run-rich-text-section rich-text-section',
        titleClassName: 'first-run-rich-text-section-title rich-text-section-title'
    });
    const body = renderModalBody(uiHtml`
        <div class="first-run-rich-text plugins-first-run-copy">
            ${richText}
        </div>
    `);
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.close') })
    });
    return createModalElement({
        id: modalId,
        rootAttributes: { 'data-page-scope': 'plugins' },
        header,
        body,
        footer
    });
};

const createPluginsIntroModalDefinition = (storage: FirstRunStateStorage): ModalDefinition => {
    return {
        id: PLUGINS_INTRO_MODAL_ID,
        layout: 'md',
        initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
        createElement: (_options: ModalOpenOptions): HTMLElement => createPluginsIntroModalElement(),
        onClose: (_modal, _options): void => {
            if (readFirstRunModalStateStatus(storage, 'pluginsIntro') !== 'pending') {
                return;
            }
            setFirstRunModalDismissed(storage, 'pluginsIntro', Date.now());
        }
    };
};

export { PLUGINS_INTRO_MODAL_ID, createPluginsIntroModalDefinition };
