/* SoAI - Plugins feature first run registration [frontend/assets/ts/features/plugins/firstRunRegistration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FirstRunModalRegistration } from '@core/firstrun/protocols.ts';
import { PLUGINS_INTRO_MODAL_ID } from '@features/plugins/modals/pluginsIntroModal.ts';

const PLUGINS_INTRO_FIRST_RUN_REGISTRATION: FirstRunModalRegistration = Object.freeze({
    id: 'pluginsIntro',
    pageId: 'plugins',
    modalId: PLUGINS_INTRO_MODAL_ID,
    allowManualOpen: false
});

export { PLUGINS_INTRO_FIRST_RUN_REGISTRATION };
