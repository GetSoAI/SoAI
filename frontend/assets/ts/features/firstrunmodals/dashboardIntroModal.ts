/* SoAI - First run modals feature dashboard intro modal [frontend/assets/ts/features/firstrunmodals/dashboardIntroModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FirstRunModalRegistration, FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import { readFirstRunModalStateStatus, setFirstRunModalDismissed } from '@core/firstrun/state.ts';
import { hardwareSnapshotHasGpu } from '@core/hardwareSnapshot.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { unwrapResourceSnapshotValue } from '@core/realtime/resourceSnapshotWait.ts';
import { HARDWARE } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import { renderStructuredTextSections, type StructuredTextSection } from '@core/richtextrenderer/structuredSections.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DashboardIntroProductContribution } from '@features/firstrunmodals/dashboardIntroProduct.ts';

const DASHBOARD_INTRO_MODAL_ID = 'dashboard-intro-modal';

interface DashboardIntroStreamManager {
    getResource(resourceName: string, options?: { state?: boolean }): JsonValue | ResourceSnapshot | null;
}

interface DashboardIntroDriverPresenceState {
    detectedGpu: boolean | null;
}

interface DashboardIntroModalDefinitionDependencies {
    storage: FirstRunStateStorage;
    driverPresence: DashboardIntroDriverPresenceState;
    product: DashboardIntroProductContribution | null;
    streamManager: DashboardIntroStreamManager;
}

interface DashboardIntroFirstRunRegistrationDependencies {
    driverPresence: DashboardIntroDriverPresenceState;
    product: DashboardIntroProductContribution | null;
}

const createDashboardIntroDriverPresenceState = (): DashboardIntroDriverPresenceState => ({
    detectedGpu: null
});

const createDashboardIntroFirstRunRegistration = (dependencies: DashboardIntroFirstRunRegistrationDependencies): FirstRunModalRegistration =>
    Object.freeze({
        id: 'dashboardIntro',
        pageId: 'dashboard',
        modalId: DASHBOARD_INTRO_MODAL_ID,
        allowManualOpen: false,
        prepare: async (options: { signal?: AbortSignal } = {}): Promise<void> => {
            if (dependencies.product === null || !dependencies.product.isAvailable()) {
                dependencies.driverPresence.detectedGpu = false;
                return;
            }
            dependencies.driverPresence.detectedGpu = await dependencies.product.prepare(options);
        }
    });

const createIntroSection = (): StructuredTextSection => ({
    id: 'start',
    getTitle: () => i18n.t('dashboard.firstRun.sections.start.sectionTitle'),
    getHeading: () => i18n.t('dashboard.firstRun.sections.start.heading'),
    blocks: [
        { type: 'paragraph', getText: () => i18n.t('dashboard.firstRun.sections.start.summary') },
        { type: 'paragraph', getText: () => i18n.t('dashboard.firstRun.sections.start.remoteSummary') }
    ]
});

const createPluginsSection = (): StructuredTextSection => ({
    id: 'plugins',
    getTitle: () => i18n.t('dashboard.firstRun.sections.plugins.sectionTitle'),
    getHeading: () => i18n.t('dashboard.firstRun.sections.plugins.heading'),
    blocks: [
        {
            type: 'list',
            items: [() => i18n.t('dashboard.firstRun.sections.plugins.review'), () => i18n.t('dashboard.firstRun.sections.plugins.localBackends'), () => i18n.t('dashboard.firstRun.sections.plugins.remoteExternal')]
        }
    ]
});

const createModelsSection = (): StructuredTextSection => ({
    id: 'models',
    getTitle: () => i18n.t('dashboard.firstRun.sections.models.sectionTitle'),
    getHeading: () => i18n.t('dashboard.firstRun.sections.models.heading'),
    blocks: [
        {
            type: 'list',
            items: [() => i18n.t('dashboard.firstRun.sections.models.localModels'), () => i18n.t('dashboard.firstRun.sections.models.remoteProviders')]
        }
    ]
});

const createUpdatesSection = (): StructuredTextSection => ({
    id: 'updates',
    getTitle: () => i18n.t('dashboard.firstRun.sections.updates.sectionTitle'),
    getHeading: () => i18n.t('dashboard.firstRun.sections.updates.headingStandard'),
    blocks: [
        {
            type: 'list',
            items: [() => i18n.t('dashboard.firstRun.sections.updates.soai'), () => i18n.t('dashboard.firstRun.sections.updates.pluginBackends')]
        }
    ]
});

const readHardwareSnapshot = (streamManager: DashboardIntroStreamManager): JsonValue | null | undefined => {
    const state = streamManager.getResource(HARDWARE, { state: true });
    return unwrapResourceSnapshotValue(state);
};

const createDashboardIntroSections = (dependencies: DashboardIntroModalDefinitionDependencies): readonly StructuredTextSection[] => {
    const productAvailable = dependencies.product?.isAvailable() ?? false;
    const hasGpu = dependencies.driverPresence.detectedGpu ?? hardwareSnapshotHasGpu(readHardwareSnapshot(dependencies.streamManager));
    const sections: StructuredTextSection[] = [createIntroSection()];
    if (productAvailable && hasGpu && dependencies.product !== null) {
        sections.push(dependencies.product.createDriverSection());
    }
    sections.push(createPluginsSection(), createModelsSection(), productAvailable && dependencies.product !== null ? dependencies.product.createUpdatesSection() : createUpdatesSection());
    return sections;
};

const createDashboardIntroModalElement = (dependencies: DashboardIntroModalDefinitionDependencies): HTMLElement => {
    const modalId = DASHBOARD_INTRO_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('dashboard.firstRun.title'),
        description: i18n.t('dashboard.firstRun.description'),
        closeLabel: i18n.t('common.close')
    });
    const richText = renderStructuredTextSections(createDashboardIntroSections(dependencies), {
        idPrefix: `${modalId}-section-`,
        sectionClassName: 'first-run-rich-text-section rich-text-section',
        titleClassName: 'first-run-rich-text-section-title rich-text-section-title'
    });
    const body = renderModalBody(uiHtml`<div class="first-run-rich-text dashboard-first-run-copy">${richText}</div>`);
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.close') })
    });
    return createModalElement({
        id: modalId,
        rootAttributes: { 'data-page-scope': 'dashboard' },
        header,
        body,
        footer
    });
};

const createDashboardIntroModalDefinition = (dependencies: DashboardIntroModalDefinitionDependencies): ModalDefinition => {
    return {
        id: DASHBOARD_INTRO_MODAL_ID,
        layout: 'md',
        initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
        createElement: (_options: ModalOpenOptions): HTMLElement => createDashboardIntroModalElement(dependencies),
        onClose: (_modal, _options): void => {
            if (readFirstRunModalStateStatus(dependencies.storage, 'dashboardIntro') !== 'pending') {
                return;
            }
            setFirstRunModalDismissed(dependencies.storage, 'dashboardIntro', Date.now());
        }
    };
};

export { DASHBOARD_INTRO_MODAL_ID, createDashboardIntroDriverPresenceState, createDashboardIntroFirstRunRegistration, createDashboardIntroModalDefinition };
export type { DashboardIntroDriverPresenceState, DashboardIntroFirstRunRegistrationDependencies, DashboardIntroModalDefinitionDependencies, DashboardIntroStreamManager };
