/* SoAI - Chat preset library modal input bindings [frontend/assets/ts/pages/chat/controllers/chatpage/configuration/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { CONTEXT_WINDOW_PRESET_ACTION, isContextWindowPresetAction, readContextWindowPreset } from '@core/chat/parameters/contextWindowPresets.ts';
import { dom } from '@core/dom/dom.ts';
import { createElementResolver } from '@core/dom/elementResolver.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import { requireInputElement } from '@core/dom/typedElements.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { setControlDisabledStateForEach } from '@core/ui/controls/disabledState.ts';
import { CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID, CHAT_PRESET_SECTION_DEFINITIONS } from '@features/chat/public.ts';
import { isChatActionId, isChatHostedActionId } from '@pages/chat/actions.ts';
import { dispatchResolvedActionCandidate } from '@pages/chat/controllers/page/events/dispatch.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { attachChatConfigurationCloseGuards } from '@pages/chat/controllers/chatpage/configuration/guards.ts';
import type { ChatConfigurationController } from '@pages/chat/controllers/chatconfigurationcontroller/ChatConfigurationController.ts';
import { isChatModelControlAction } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlWidget.ts';
import { CHAT_MODEL_CONTROL_ROOT_SELECTOR, requireChatModelControlScopeFromRoot, resolveClosestChatModelControlRoot } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts';
import { CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuSearchWidget.ts';

interface ChatConfigurationInputBindingsHost {
    handleModelSearchInput(input: HTMLInputElement): void;
    closeModelMenu(): void;
    updateMemorySearch(value: string): void;
    updatePresetSearch(value: string): void;
    updatePresetName(value: string): void;
    updatePresetSection(sectionId: (typeof CHAT_PRESET_SECTION_DEFINITIONS)[number]['id'], selected: boolean): void;
}

interface ChatConfigurationModalEventsHost {
    configuration: ChatConfigurationController;
    hasPresetDraft(): boolean;
    handleModelAction(actionElement: HTMLElement): void;
    openConfiguration(modal: HTMLElement): void;
    closeConfiguration(): void;
    localizeConfiguration(): void;
    setDefaultToolsExpanded(expanded: boolean): void;
}

const bindChatConfigurationModalEvents = (host: ChatConfigurationModalEventsHost, signal: AbortSignal, getRootEventsHost: () => ChatRootEventsHost | null): void => {
    const bindModal = (modalId: string, onOpen: (modal: HTMLElement) => void, onClose: () => void, requireInitialActions: boolean): void => {
        const modal = requireModalPresenter().requireElement(modalId);
        const elements = createElementResolver(modal, 'Chat configuration');
        const syncPresetButtons = (): void => {
            if (modalId !== CHAT_CONFIGURATION_MODAL_ID) return;
            const buttons = dom.resolveAll(`[data-action="${CONTEXT_WINDOW_PRESET_ACTION}"]`, modal).map((element) => narrowButton(element, 'Context-window preset'));
            setControlDisabledStateForEach(buttons, !host.configuration.isEditingConfiguration() || !host.configuration.operationGate().canAcquire());
        };
        if (modalId === CHAT_CONFIGURATION_MODAL_ID) {
            attachChatConfigurationCloseGuards({ modal, configuration: host.configuration, hasPresetDraft: host.hasPresetDraft, signal });
            signal.addEventListener('abort', host.configuration.operationGate().subscribe(syncPresetButtons), { once: true });
            syncPresetButtons();
        }
        const handleOpen = (): void => {
            onOpen(modal);
            syncPresetButtons();
        };
        const handleClose = (): void => {
            onClose();
            syncPresetButtons();
        };
        modal.addEventListener('core.modal.open', handleOpen, { signal });
        modal.addEventListener('core.modal.close', handleClose, { signal });
        modal.addEventListener('core.modal.localize', host.localizeConfiguration, { signal });
        bindPageActionDispatcher({
            root: modal,
            signal,
            label: `ChatPage ${modalId}`,
            isAction: isChatHostedActionId,
            assertKnownActions: requireInitialActions,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    ignorePrevented: true,
                    onAction: ({ event, action, actionElement }): void => {
                        if (routeConfigurationModelControlAction({ action, actionElement, event, handle: () => host.handleModelAction(actionElement) })) return;
                        const rootHost = getRootEventsHost();
                        if (isContextWindowPresetAction(action)) {
                            event.preventDefault();
                            if (modalId !== CHAT_CONFIGURATION_MODAL_ID || !rootHost || !host.configuration.isEditingConfiguration() || !host.configuration.operationGate().canAcquire()) return;
                            const input = requireInputElement(elements, modalUiSelector(modalId, 'chat-model-context-window-tokens-input'), 'Chat configuration context-window input');
                            if (input.disabled || input.readOnly) return;
                            input.value = String(readContextWindowPreset(actionElement));
                            rootHost.composer.applyParameterValueFromElement(input);
                            return;
                        }
                        if (rootHost && isChatActionId(action) && !(actionElement instanceof HTMLInputElement) && !(actionElement instanceof HTMLSelectElement) && !(actionElement instanceof HTMLTextAreaElement)) dispatchResolvedActionCandidate(rootHost, event, { action, actionElement });
                    }
                }
            }
        });
    };
    bindModal(CHAT_CONFIGURATION_MODAL_ID, host.openConfiguration, host.closeConfiguration, true);
    bindModal(
        CHAT_MCP_DEFAULT_TOOLS_MODAL_ID,
        () => host.setDefaultToolsExpanded(true),
        () => host.setDefaultToolsExpanded(false),
        false
    );
};

const bindChatConfigurationInputs = (host: ChatConfigurationInputBindingsHost, modal: HTMLElement, signal: AbortSignal): void => {
    modal.addEventListener(
        'input',
        (event) => {
            const input = event.target;
            if (!(input instanceof HTMLInputElement)) return;
            if (input.matches(CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR)) host.handleModelSearchInput(input);
            else if (input.id === modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'memory-search')) host.updateMemorySearch(input.value);
            else if (input.id === modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'preset-search')) host.updatePresetSearch(input.value);
            else if (input.dataset['chatPresetEditorName'] === 'true') host.updatePresetName(input.value);
        },
        { signal }
    );
    modal.addEventListener(
        'change',
        (event) => {
            const input = event.target;
            if (!(input instanceof HTMLInputElement) || input.type !== 'checkbox') return;
            const sectionId = input.dataset['chatPresetSection'];
            const definition = CHAT_PRESET_SECTION_DEFINITIONS.find((candidate) => candidate.id === sectionId);
            if (definition) host.updatePresetSection(definition.id, input.checked);
        },
        { signal }
    );
    modal.addEventListener(
        'click',
        (event) => {
            const target = event.target;
            const controlRoot = dom.resolve(CHAT_MODEL_CONTROL_ROOT_SELECTOR, modal);
            if (target instanceof Node && controlRoot?.contains(target)) return;
            host.closeModelMenu();
        },
        { signal }
    );
};

const routeConfigurationModelControlAction = (inputArguments: { action: string | undefined; actionElement: HTMLElement; event: Event; handle(): void }): boolean => {
    if (!isChatModelControlAction(inputArguments.action)) {
        return false;
    }
    const root = resolveClosestChatModelControlRoot(inputArguments.actionElement);
    if (root === null || requireChatModelControlScopeFromRoot(root) !== 'configuration') {
        return false;
    }
    inputArguments.event.preventDefault();
    inputArguments.handle();
    return true;
};

export { bindChatConfigurationInputs, bindChatConfigurationModalEvents, routeConfigurationModelControlAction };
export type { ChatConfigurationInputBindingsHost, ChatConfigurationModalEventsHost };
