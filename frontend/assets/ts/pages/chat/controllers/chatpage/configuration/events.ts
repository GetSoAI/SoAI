/* SoAI - Chat preset library modal input bindings [frontend/assets/ts/pages/chat/controllers/chatpage/configuration/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';
import { dom } from '@core/dom/dom.ts';
import { CHAT_CONFIGURATION_MODAL_ID, CHAT_PRESET_SECTION_DEFINITIONS } from '@features/chat/public.ts';
import { isChatModelControlAction } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlWidget.ts';
import { CHAT_MODEL_CONTROL_ROOT_SELECTOR, requireChatModelControlScopeFromRoot, resolveClosestChatModelControlRoot } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts';
import { CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuSearchWidget.ts';

interface ChatConfigurationInputBindingsHost {
    handleModelSearchInput(input: HTMLInputElement): void;
    closeModelMenu(): void;
    updatePresetSearch(value: string): void;
    updatePresetName(value: string): void;
    updatePresetSection(sectionId: (typeof CHAT_PRESET_SECTION_DEFINITIONS)[number]['id'], selected: boolean): void;
}

const bindChatConfigurationInputs = (host: ChatConfigurationInputBindingsHost, modal: HTMLElement, signal: AbortSignal): void => {
    modal.addEventListener(
        'input',
        (event) => {
            const input = event.target;
            if (!(input instanceof HTMLInputElement)) return;
            if (input.matches(CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR)) host.handleModelSearchInput(input);
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

export { bindChatConfigurationInputs, routeConfigurationModelControlAction };
export type { ChatConfigurationInputBindingsHost };
