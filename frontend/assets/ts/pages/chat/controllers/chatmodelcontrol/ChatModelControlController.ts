/* SoAI - Shared chat model-control interaction ownership [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/ChatModelControlController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasDataActionElement } from '@core/dom/dataAction.ts';
import { MODELS_ACTION_DOWNLOAD_MODEL } from '@core/models/pageActions.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { CHAT_COMPARISON_MAX_EFFECTIVE_MODELS } from '@core/chat/comparisonModels.ts';
import type { Conversation } from '@features/chat/public.ts';
import { CHAT_MODEL_CONTROL_ACTION_ADD_MODEL, CHAT_MODEL_CONTROL_ACTION_REMOVE_MODEL, CHAT_MODEL_CONTROL_ACTION_SELECT_MODEL, CHAT_MODEL_CONTROL_ACTION_TOGGLE_MENU, type ModelControlMenuOpenState, type ModelControlScope } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlWidget.ts';
import { parseChatModelControlSlotIndex, requireChatModelControlScopeFromRoot, resolveClosestChatModelControlRoot } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts';
import { ChatModelControlRenderController } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlRenderController.ts';
import { applyChatModelMenuSearchInput, CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuSearchWidget.ts';
import { normalizeChatModelId, resolveNextComparisonModelId, type EffectiveModels } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type ModelControlHost = PageDomOwnerHost & {
    pageContext: { sanitizer: SanitizerApi };
    getCachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    models: ModelData[];
    modelIndex: Map<string, ModelData>;
    modelStreamHasPayload: boolean;
    hasSelectableModels(): boolean;
    getCurrentConversation(): Conversation | null;
    navigateWithQuery(page: string, query: Record<string, string>): void;
    isConversationExecuting(conversationId: string): boolean;
    isModelSelectionLocked(): boolean;
    resolveChatModelControlRoots(): HTMLElement[];
    resolveModelControlOverlayBoundary(): HTMLElement | null;
    resolveEffectiveModels(): EffectiveModels;
    applyEffectiveModels(models: EffectiveModels): Promise<void>;
    updateModelUI(): void;
};

export class ChatModelControlController {
    readonly #host: ModelControlHost;
    readonly #renderController: ChatModelControlRenderController;
    #openMenu: ModelControlMenuOpenState = null;
    #menuSearchQuery = '';

    constructor(host: ModelControlHost) {
        this.#host = host;
        this.#renderController = new ChatModelControlRenderController(host);
    }

    render(): void {
        this.#openMenu = this.#renderController.render(this.#openMenu, this.#menuSearchQuery);
        this.#resetSearchWhenClosed();
    }

    closeMenu(): void {
        if (this.#openMenu === null) {
            this.#menuSearchQuery = '';
            return;
        }
        this.#openMenu = null;
        this.#menuSearchQuery = '';
        this.#openMenu = this.#renderController.renderOpenMenuState(this.#openMenu, this.#menuSearchQuery);
        this.#resetSearchWhenClosed();
    }

    handleAction(actionElement: HTMLElement): Promise<void> | void {
        if (!hasDataActionElement(actionElement) || this.#host.isModelSelectionLocked()) {
            return;
        }
        const action = actionElement.dataset.action;
        if (action === CHAT_MODEL_CONTROL_ACTION_TOGGLE_MENU) {
            this.#handleToggleMenu(actionElement);
            return;
        }
        if (action === CHAT_MODEL_CONTROL_ACTION_SELECT_MODEL) {
            return this.#handleSelectModel(actionElement);
        }
        if (action === CHAT_MODEL_CONTROL_ACTION_ADD_MODEL) {
            return this.#handleAddModel(actionElement);
        }
        if (action === CHAT_MODEL_CONTROL_ACTION_REMOVE_MODEL) {
            return this.#handleRemoveModel(actionElement);
        }
    }

    handleSearchInput(input: HTMLInputElement): void {
        if (!input.matches(CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR)) {
            throw new Error('Chat model control search requires the menu search input');
        }
        if (this.#openMenu === null) {
            throw new Error('Chat model control search requires an open menu');
        }
        this.#menuSearchQuery = applyChatModelMenuSearchInput(input);
    }

    #handleToggleMenu(actionElement: HTMLElement): void {
        if (actionElement.getAttribute('aria-disabled') === 'true' || actionElement.getAttribute('data-toggle-disabled') === 'true') {
            return;
        }
        const scope = this.#requireActionScope(actionElement);
        const slotIndex = parseChatModelControlSlotIndex(actionElement);
        const existing = this.#openMenu;
        if (existing && existing.scope === scope && existing.slotIndex === slotIndex) {
            this.#openMenu = null;
            this.#menuSearchQuery = '';
        } else {
            if (!existing || existing.scope !== scope || existing.slotIndex !== slotIndex) {
                this.#menuSearchQuery = '';
            }
            this.#openMenu = { scope, slotIndex };
        }
        this.#openMenu = this.#renderController.renderOpenMenuState(this.#openMenu, this.#menuSearchQuery);
        this.#resetSearchWhenClosed();
    }

    async #handleSelectModel(actionElement: HTMLElement): Promise<void> {
        if (this.#renderController.isCurrentConversationExecuting()) {
            return;
        }
        const nextModelId = normalizeChatModelId(actionElement.getAttribute('data-model-id'));
        if (!nextModelId) {
            throw new Error('Chat model selection requires a model id');
        }
        const model = this.#host.modelIndex.get(nextModelId);
        if (!model || !isChatSelectableModel(model)) {
            return;
        }
        const slotIndex = parseChatModelControlSlotIndex(actionElement);
        this.#requireActionScope(actionElement);
        const effective = this.#host.resolveEffectiveModels();
        if (slotIndex > 0 && this.#host.getCurrentConversation() === null) {
            return;
        }
        const next = { primary: effective.primary, comparison: [...effective.comparison] };
        if (slotIndex === 0) {
            next.primary = nextModelId;
        } else {
            const comparisonIndex = slotIndex - 1;
            if (comparisonIndex < 0 || comparisonIndex >= next.comparison.length) {
                throw new Error('Chat model slot index is out of range');
            }
            next.comparison[comparisonIndex] = nextModelId;
        }
        await this.#applyModels(next, null);
    }

    async #handleAddModel(actionElement: HTMLElement): Promise<void> {
        const host = this.#host;
        if (!host.hasSelectableModels()) {
            this.#openMenu = null;
            this.#menuSearchQuery = '';
            this.render();
            host.navigateWithQuery('models', { action: MODELS_ACTION_DOWNLOAD_MODEL });
            return;
        }
        if (this.#renderController.isCurrentConversationExecuting()) {
            return;
        }
        if (host.getCurrentConversation() === null) {
            return;
        }
        const effective = host.resolveEffectiveModels();
        const effectiveSlotCount = 1 + effective.comparison.length;
        const primary = normalizeChatModelId(effective.primary);
        if (!primary || effectiveSlotCount >= CHAT_COMPARISON_MAX_EFFECTIVE_MODELS) {
            return;
        }
        const nextModelId = resolveNextComparisonModelId({ models: host.models, primary, comparison: effective.comparison });
        const scope = this.#requireActionScope(actionElement);
        await this.#applyModels({ primary, comparison: [...effective.comparison, nextModelId] }, { scope, slotIndex: effectiveSlotCount });
    }

    async #handleRemoveModel(actionElement: HTMLElement): Promise<void> {
        if (this.#renderController.isCurrentConversationExecuting()) {
            return;
        }
        if (this.#host.getCurrentConversation() === null) {
            return;
        }
        const slotIndex = parseChatModelControlSlotIndex(actionElement);
        this.#requireActionScope(actionElement);
        const effective = this.#host.resolveEffectiveModels();
        const primary = normalizeChatModelId(effective.primary);
        if (!primary) {
            return;
        }
        if (slotIndex === 0) {
            const nextPrimary = normalizeChatModelId(effective.comparison[0] ?? null);
            if (!nextPrimary) {
                return;
            }
            await this.#applyModels({ primary: nextPrimary, comparison: effective.comparison.slice(1) }, null);
            return;
        }
        const comparisonIndex = slotIndex - 1;
        if (comparisonIndex < 0 || comparisonIndex >= effective.comparison.length) {
            throw new Error('Chat model slot index is out of range');
        }
        await this.#applyModels({ primary, comparison: effective.comparison.filter((_modelId, index) => index !== comparisonIndex) }, null);
    }

    async #applyModels(models: EffectiveModels, openMenu: ModelControlMenuOpenState): Promise<void> {
        await this.#host.applyEffectiveModels(models);
        this.#openMenu = openMenu;
        this.#menuSearchQuery = '';
        this.render();
        this.#host.updateModelUI();
    }

    #resetSearchWhenClosed(): void {
        if (this.#openMenu === null) {
            this.#menuSearchQuery = '';
        }
    }

    #requireActionScope(actionElement: HTMLElement): ModelControlScope {
        const root = resolveClosestChatModelControlRoot(actionElement);
        if (root === null) {
            throw new Error('Chat model control action requires a control root');
        }
        return requireChatModelControlScopeFromRoot(root);
    }
}
