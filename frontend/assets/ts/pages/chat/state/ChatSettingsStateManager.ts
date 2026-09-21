/* SoAI - Chat settings and preference state ownership [frontend/assets/ts/pages/chat/state/ChatSettingsStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatUiStorage } from '@core/chat/protocols.ts';
import { getDefaultChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { TextZoomController } from '@core/TextZoomController.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ChatParameters } from '@features/chat/public.ts';
import { DEFAULT_TEXT_ZOOM } from '@pages/chat/contracts/chatPageConfig.ts';
import { EXCLUDED_REQUEST_PARAMETER_KEY_SET } from '@core/chat/parameters/chatParameterKeySets.ts';
import { buildChatRequestParameters } from '@core/chat/parameters/chatRequestParameters.ts';
import { isInlineMultimediaPreviewsEnabled, isRichTextEnabled, isShowActivitiesEnabled, isShowActivityElapsedTimeEnabled } from '@pages/chat/controllers/page/state.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ChatTextZoomPageHost extends PageDomOwnerHost {
    dom: {
        getDocumentElement: () => HTMLElement;
    };
}

class ChatSettingsState {
    backendPreferences: JsonObject | null = null;
    backendPreferencesGeneration = 0;
    backendPreferencesStale = false;
    backendPreferencesLoad: Promise<void> | null = null;
    #parameters: ChatParameters = getDefaultChatParameters();
    parametersGeneration = 0;
    textZoom = DEFAULT_TEXT_ZOOM;
    readonly textZoomController: TextZoomController;
    textZoomInitialized = false;
    readonly storage: ChatUiStorage;
    readonly textZoomPageHost: ChatTextZoomPageHost;

    constructor(storage: ChatUiStorage, textZoomController: TextZoomController, textZoomPageHost: ChatTextZoomPageHost) {
        this.storage = storage;
        this.textZoomController = textZoomController;
        this.textZoomPageHost = textZoomPageHost;
    }

    get parameters(): ChatParameters {
        return this.#parameters;
    }

    set parameters(parameters: ChatParameters) {
        this.#parameters = parameters;
        this.parametersGeneration += 1;
    }

    applyAuthoritativeParameters(parameters: ChatParameters, capturedGeneration: number): boolean {
        if (this.parametersGeneration !== capturedGeneration) return false;
        this.#parameters = parameters;
        return true;
    }

    applyAuthoritativeBackendPreferences(preferences: JsonObject): void {
        this.backendPreferences = preferences;
        this.backendPreferencesGeneration += 1;
        this.backendPreferencesStale = false;
    }

    applyNarrowBackendPreferences(preferences: JsonObject, capturedGeneration: number): boolean {
        if (this.backendPreferencesGeneration !== capturedGeneration) return false;
        this.applyAuthoritativeBackendPreferences(preferences);
        return true;
    }

    applyTextZoom(): void {
        this.textZoom = this.textZoomController.applyZoom(this.textZoomPageHost);
    }

    requestParameters(): JsonObject {
        return buildChatRequestParameters(this.parameters, EXCLUDED_REQUEST_PARAMETER_KEY_SET);
    }

    richTextEnabled(): boolean {
        return isRichTextEnabled(this.parameters);
    }

    inlineMultimediaPreviewsEnabled(): boolean {
        return isInlineMultimediaPreviewsEnabled(this.parameters);
    }

    showActivitiesEnabled(): boolean {
        return isShowActivitiesEnabled(this.parameters);
    }

    showActivityElapsedTimeEnabled(): boolean {
        return isShowActivityElapsedTimeEnabled(this.parameters);
    }
}

export { ChatSettingsState };
export type { ChatTextZoomPageHost };
export interface ChatSettingsStateHost {
    settings: ChatSettingsState;
}
