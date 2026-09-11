/* SoAI - Core frontend edition composition [frontend/assets/ts/app/edition/coreFrontendEdition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FrontendEditionComposition } from '@app/edition/frontendEditionComposition.ts';
import { BASE_BRANDING } from '@core/branding/constants.ts';
import { i18n } from '@core/i18n/index.ts';
import { CORE_BACKGROUND_ACTIVITY_OPERATION_TYPES } from '@core/tasks/backgroundActivityPolicy.ts';

const CORE_FRONTEND_EDITION: FrontendEditionComposition = Object.freeze({
    edition: 'soai-core',
    routes: Object.freeze([]),
    pages: Object.freeze([]),
    modalDefinitions: Object.freeze([]),
    createHostManagementApi: () => null,
    settings: null,
    licensing: Object.freeze({
        purchaseUrl: 'https://soai.to/licensing',
        contactUrl: 'https://soai.to/contact',
        getEditionLabel: () => i18n.t('licensing.base.product'),
        getWelcomeHeading: () => i18n.t('wizard.welcome.heading'),
        getProductLabel: () => i18n.t('licensing.base.product'),
        getPurchaseLabel: () => i18n.t('licensing.base.purchase'),
        getContactLabel: () => i18n.t('licensing.base.contact'),
        getAccessSummary: () => i18n.t('licensing.base.accessSummary'),
        getPersonalOffer: () => null
    }),
    dashboard: null,
    updates: null,
    userSyncSections: Object.freeze([]),
    services: Object.freeze([]),
    translationCatalogs: Object.freeze([]),
    taskCatalog: Object.freeze({
        taskTypeMappings: Object.freeze({}),
        operationLabels: Object.freeze({}),
        backgroundActivityOperationTypes: CORE_BACKGROUND_ACTIVITY_OPERATION_TYPES
    }),
    branding: BASE_BRANDING,
    createDashboardIntro: () => null
});

export { CORE_FRONTEND_EDITION };
