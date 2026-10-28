/* SoAI - Settings speech-to-text model card [frontend/assets/ts/pages/settings/controllers/speechmodel/SpeechModelSettingsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { requireSpeechSetup } from '@core/speechsetup/service.ts';
import { mountSpeechSetup } from '@core/speechsetup/view.ts';
import { renderSpeechModelSettings, SPEECH_MODEL_SETTINGS_ID } from '@pages/settings/controllers/speechmodel/view.ts';

interface SpeechModelSettingsDependencies {
    host: PageDomOwnerHost;
    readSavedSelector: () => string;
}

class SpeechModelSettingsManager {
    readonly #host: PageDomOwnerHost;
    readonly #readSavedSelector: () => string;
    #mountController: AbortController | null = null;

    constructor({ host, readSavedSelector }: SpeechModelSettingsDependencies) {
        this.#host = host;
        this.#readSavedSelector = readSavedSelector;
    }

    render(): TrustedHtml {
        return renderSpeechModelSettings(this.#readSavedSelector(), requireSpeechSetup().snapshot('media').models);
    }

    setupEventListeners(): void {
        this.dispose();
        const card = this.#host.pageDom.require(SPEECH_MODEL_SETTINGS_ID);
        const controller = new AbortController();
        this.#mountController = controller;
        mountSpeechSetup(card, controller.signal);
    }

    dispose(): void {
        this.#mountController?.abort();
        this.#mountController = null;
    }
}

export { SpeechModelSettingsManager };
export type { SpeechModelSettingsDependencies };
