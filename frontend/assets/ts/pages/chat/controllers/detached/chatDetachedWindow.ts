/* SoAI - Chat page control layer detached window [frontend/assets/ts/pages/chat/controllers/detached/chatDetachedWindow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { openDetachedRuntimeWindow } from '@core/runtimeenv/public.ts';
import { isJsonValue, type JsonObject } from '@core/types/jsonValues.ts';
import { isBoolean, isString } from '@core/typeGuards.ts';
import type { ChatParameters } from '@features/chat/public.ts';
import { normalizeDetachedBootstrapParameters } from '@pages/chat/controllers/detached/chatDetachedBootstrap.ts';

interface DetachedWindowRuntimePort {
    isDetached: () => boolean;
    optionalUI: (selector: string | Element, context?: Element) => Element | null;
    dom: { setStyle(element: HTMLElement, prop: string, value: string | null): void };
    flushComposerDraft: (reason: string) => Promise<void>;
}

interface DetachedWindowStatePort {
    hasConversation: (conversationId: string) => boolean;
    getCurrentConversationId: () => string | null;
    setCurrentConversationId: (conversationId: string | null) => void;
    getCurrentModel: () => string | null;
    setCurrentModel: (modelId: string | null) => void;
    getSidebarOpen: () => boolean;
    setSidebarOpen: (open: boolean) => void;
    getTextZoom: () => number;
    setTextZoom: (zoom: number) => void;
    getSearchQuery: () => string;
    setSearchQuery: (query: string) => void;
    getParameters: () => ChatParameters;
    setParameters: (parameters: ChatParameters) => void;
}

interface DetachedWindowPresentationPort {
    validateTextZoomValue: (zoom: number | null, contextMessage: string) => number | null;
    persistTextZoom: (zoom: number) => void;
    applyTextZoom: () => void;
    applySidebarState: () => void;
    applyWidescreenMode: () => void;
    updateModelUI: () => void;
    getInputElement: () => Element | null;
    noteChatInputDraftChanged: (value: string) => void;
    updateInputState: () => void;
    updateParameterUi: () => void;
    updateSearchBar: (value: string) => void;
}

interface DetachedWindowHost {
    runtime: DetachedWindowRuntimePort;
    state: DetachedWindowStatePort;
    presentation: DetachedWindowPresentationPort;
}

const openChatDetachedWindow = (host: DetachedWindowHost): void => {
    const openWindow = (): void => {
        openDetachedRuntimeWindow('chat', {
            title: i18n.t('chat.detached.windowTitle'),
            parameters: buildDetachedLaunchParameters(host)
        });
    };
    void host.runtime
        .flushComposerDraft('detached-open')
        .then(openWindow)
        .catch((error) => {
            errorHandler.warn('ChatPage', 'Failed to flush composer draft before detached window handoff', ensureError(error));
            openWindow();
        });
};

const buildDetachedLaunchParameters = (host: DetachedWindowHost): JsonObject => {
    const conversationId = isString(host.state.getCurrentConversationId()) ? host.state.getCurrentConversationId() : undefined;
    const modelId = isString(host.state.getCurrentModel()) ? host.state.getCurrentModel() : undefined;
    const inputCandidate = host.presentation.getInputElement();
    const inputElement = inputCandidate instanceof HTMLTextAreaElement || inputCandidate instanceof HTMLInputElement ? inputCandidate : null;
    const draftMessageValue = inputElement ? inputElement.value : '';
    const draftMessage = draftMessageValue ? draftMessageValue : undefined;
    const chatParameters: JsonObject = {};
    for (const [key, value] of Object.entries(cloneChatParameters(host.state.getParameters()))) {
        if (isJsonValue(value)) {
            chatParameters[key] = value;
        }
    }
    const launchParameters: JsonObject = {
        sidebarOpen: true,
        'text_zoom': host.state.getTextZoom(),
        searchQuery: host.state.getSearchQuery(),
        parameters: chatParameters,
        'widescreen_mode': Boolean(host.state.getParameters().widescreenMode)
    };
    if (conversationId) launchParameters['conversationId'] = conversationId;
    if (modelId) launchParameters['model_id'] = modelId;
    if (draftMessage) launchParameters['draftMessage'] = draftMessage;
    return launchParameters;
};

const configureDetachedEnvironment = (host: DetachedWindowHost, parameters: JsonObject = {}): void => {
    if (!host.runtime.isDetached()) {
        return;
    }
    applyDetachedBootstrapState(host, parameters);
};

const applyDetachedBootstrapState = (host: DetachedWindowHost, parameters: JsonObject = {}): void => {
    const norm = normalizeDetachedBootstrapParameters(parameters);
    if (norm.sidebarOpen !== null) host.state.setSidebarOpen(norm.sidebarOpen);
    if (norm.textZoom !== null) {
        const zoom = host.presentation.validateTextZoomValue(norm.textZoom, 'Invalid detached chat text zoom');
        if (zoom !== null) {
            host.state.setTextZoom(zoom);
            host.presentation.persistTextZoom(zoom);
        }
    }
    if (norm.parameters) {
        const parameters = host.state.getParameters();
        host.state.setParameters(cloneChatParameters({ ...parameters, ...norm.parameters }));
    }
    const updatedParameters = host.state.getParameters();
    if (isBoolean(norm.widescreenMode)) updatedParameters.widescreenMode = norm.widescreenMode;
    if (norm.modelId) host.state.setCurrentModel(norm.modelId);
    if (norm.searchQuery) {
        host.state.setSearchQuery(norm.searchQuery);
    }
    if (norm.draftMessage !== null) {
        const input = host.presentation.getInputElement();
        if (input instanceof HTMLTextAreaElement || input instanceof HTMLInputElement) {
            input.value = norm.draftMessage;
            host.presentation.noteChatInputDraftChanged(norm.draftMessage);
        }
    }
    host.presentation.applyTextZoom();
    host.presentation.applySidebarState();
    host.presentation.updateSearchBar(host.state.getSearchQuery());
    host.presentation.updateModelUI();
    host.presentation.updateParameterUi();
    host.presentation.updateInputState();
};

export type { DetachedWindowHost };
export { openChatDetachedWindow, configureDetachedEnvironment };
