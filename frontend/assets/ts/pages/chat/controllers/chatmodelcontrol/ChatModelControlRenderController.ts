/* SoAI - Chat page model control render controller [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/ChatModelControlRenderController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';
import { dom } from '@core/dom/dom.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import { normalizeConversationId, type Conversation } from '@features/chat/public.ts';
import { resolveConversationAuthorityLock, type ConversationAuthorityLock } from '@core/chat/conversationAuthorityLock.ts';
import { renderChatModelControlMarkup, type ModelControlMenuOpenState, type ModelControlScope } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlWidget.ts';
import { normalizeChatModelId, type EffectiveModels } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts';
import { CHAT_MODEL_CONTROL_SELECTOR, CHAT_MODEL_MENU_SELECTOR, CHAT_MODEL_OPEN_MENU_SELECTOR, CHAT_MODEL_OPEN_TRIGGER_SELECTOR, requireChatModelControlScopeFromRoot } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts';
import { applyChatModelMenuSearchFilter, captureChatModelMenuSearchInputState, restoreChatModelMenuSearchInputState } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuSearchWidget.ts';

const CHAT_INPUT_WRAPPER_SELECTOR = '.chat-input-wrapper';
const CHAT_MODEL_MENU_MAX_HEIGHT_PROPERTY = '--chat-model-menu-max-height';

interface ChatModelControlRenderHost extends PageDomOwnerHost {
    pageContext: { sanitizer: SanitizerApi };
    getCachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    models: ModelData[];
    modelIndex: Map<string, ModelData>;
    modelStreamHasPayload: boolean;
    hasSelectableModels(): boolean;
    getCurrentConversation(): Conversation | null;
    isConversationExecuting(conversationId: string): boolean;
    resolveChatModelControlRoots(): HTMLElement[];
    resolveModelControlOverlayBoundary(): HTMLElement | null;
    resolveEffectiveModels(): EffectiveModels;
}

type ChatModelControlRenderState = {
    nextOpenMenu: ModelControlMenuOpenState;
    effectiveModels: EffectiveModels;
    isExecuting: boolean;
    authorityLock: ConversationAuthorityLock | null;
    menuSearchQuery: string;
};

class ChatModelControlRenderController {
    readonly #host: ChatModelControlRenderHost;

    constructor(host: ChatModelControlRenderHost) {
        this.#host = host;
    }

    render(openMenu: ModelControlMenuOpenState, menuSearchQuery: string): ModelControlMenuOpenState {
        const state = this.#resolveRenderState(openMenu, menuSearchQuery);
        for (const root of this.#queryRoots()) {
            this.#renderRoot(root, state);
        }
        return state.nextOpenMenu;
    }

    renderOpenMenuState(openMenu: ModelControlMenuOpenState, menuSearchQuery: string): ModelControlMenuOpenState {
        const state = this.#resolveRenderState(openMenu, menuSearchQuery);
        for (const root of this.#queryRoots()) {
            const scope = requireChatModelControlScopeFromRoot(root);
            this.#closeRootMenu(root);
            if (state.nextOpenMenu !== null && state.nextOpenMenu.scope === scope) {
                this.#openRootMenu(root, scope, state);
            }
        }
        return state.nextOpenMenu;
    }

    #queryRoots(): HTMLElement[] {
        return this.#host.resolveChatModelControlRoots();
    }

    #resolveRenderState(openMenu: ModelControlMenuOpenState, menuSearchQuery: string): ChatModelControlRenderState {
        const host = this.#host;
        const isExecuting = this.isCurrentConversationExecuting();
        const conversation = host.getCurrentConversation();
        const effectiveModels = host.resolveEffectiveModels();
        const authorityLock = resolveConversationAuthorityLock(conversation);
        const effectiveCount = (normalizeChatModelId(effectiveModels.primary) ? 1 : 0) + effectiveModels.comparison.length;
        let nextOpenMenu = openMenu;
        if (isExecuting || authorityLock !== null) {
            nextOpenMenu = null;
        } else if (nextOpenMenu && (nextOpenMenu.slotIndex < 0 || nextOpenMenu.slotIndex >= Math.max(effectiveCount, 1))) {
            nextOpenMenu = null;
        }
        return { nextOpenMenu, effectiveModels, isExecuting, authorityLock, menuSearchQuery: nextOpenMenu === null ? '' : menuSearchQuery };
    }

    #renderRoot(root: HTMLElement, state: ChatModelControlRenderState): void {
        const scope = requireChatModelControlScopeFromRoot(root);
        const markup = this.#renderMarkup(scope, state);
        const searchInputState = captureChatModelMenuSearchInputState(root);
        this.#host.pageDom.updateHtml(root, markup, { escape: false });
        this.#syncOpenMenuHeight(root, state);
        this.#syncOpenMenuSearch(root, state);
        restoreChatModelMenuSearchInputState(root, searchInputState);
    }

    #renderMarkup(scope: ModelControlScope, state: ChatModelControlRenderState): TrustedHtml {
        const host = this.#host;
        return renderChatModelControlMarkup({
            scope,
            sanitizer: host.pageContext.sanitizer,
            getCachedIcon: (name: IconName, options?: IconOptions) => host.getCachedIcon(name, options),
            models: host.models,
            modelIndex: host.modelIndex,
            modelStreamHasPayload: host.modelStreamHasPayload,
            hasSelectableModels: host.hasSelectableModels(),
            effectiveModels: state.effectiveModels,
            isExecuting: state.isExecuting,
            authorityLock: state.authorityLock,
            openMenu: state.nextOpenMenu,
            menuSearchQuery: state.menuSearchQuery
        });
    }

    #closeRootMenu(root: HTMLElement): void {
        for (const menu of dom.resolveAll(CHAT_MODEL_MENU_SELECTOR, root)) {
            dom.remove(menu);
        }
        for (const trigger of dom.resolveAll(CHAT_MODEL_OPEN_TRIGGER_SELECTOR, root)) {
            dom.removeClass(trigger, 'is-open');
        }
    }

    #openRootMenu(root: HTMLElement, scope: ModelControlScope, state: ChatModelControlRenderState): void {
        const currentControl = dom.resolve(CHAT_MODEL_CONTROL_SELECTOR, root);
        if (!(currentControl instanceof HTMLElement) || state.nextOpenMenu === null) {
            throw new Error('Chat model control menu opening requires a rendered control and open menu state');
        }
        const nextMarkup = this.#renderMarkup(scope, state);
        const nextControl = parseSingleRootElement({
            documentRef: root.ownerDocument,
            html: nextMarkup,
            context: root
        });
        if (this.#requiresStructureRender(currentControl, nextControl)) {
            this.#host.pageDom.updateHtml(root, nextMarkup, { escape: false });
            this.#syncOpenMenuHeight(root, state);
            this.#syncOpenMenuSearch(root, state);
            return;
        }
        const nextMenu = nextControl ? dom.resolve(CHAT_MODEL_OPEN_MENU_SELECTOR, nextControl) : null;
        const trigger = this.#resolveTrigger(currentControl, state.nextOpenMenu.slotIndex);
        if (!(nextMenu instanceof HTMLElement) || !trigger) {
            throw new Error('Chat model control menu opening requires a matching trigger and menu');
        }
        dom.addClass(trigger, 'is-open');
        dom.appendChild(currentControl, nextMenu);
        this.#syncMenuHeight(nextMenu, scope);
        applyChatModelMenuSearchFilter(nextMenu, state.menuSearchQuery);
    }

    #syncOpenMenuHeight(root: HTMLElement, state: ChatModelControlRenderState): void {
        if (state.nextOpenMenu === null) {
            return;
        }
        const scope = requireChatModelControlScopeFromRoot(root);
        if (state.nextOpenMenu.scope !== scope) {
            return;
        }
        const menu = dom.resolve(CHAT_MODEL_OPEN_MENU_SELECTOR, root);
        if (!(menu instanceof HTMLElement)) {
            throw new Error('Chat model control menu height sync requires an open menu');
        }
        this.#syncMenuHeight(menu, scope);
    }

    #syncMenuHeight(menu: HTMLElement, scope: ModelControlScope): void {
        if (scope === 'empty-state') {
            this.#syncMenuHeightToBoundary(menu, this.#resolveInputWrapper());
            return;
        }
        if (scope === 'configuration') {
            this.#syncMenuHeightToBoundary(menu, this.#host.resolveModelControlOverlayBoundary());
            return;
        }
        dom.setStyle(menu, CHAT_MODEL_MENU_MAX_HEIGHT_PROPERTY, null);
    }

    #syncMenuHeightToBoundary(menu: HTMLElement, boundary: HTMLElement | null): void {
        if (!boundary) {
            dom.setStyle(menu, CHAT_MODEL_MENU_MAX_HEIGHT_PROPERTY, null);
            return;
        }
        const menuRect = measureLayoutBox(menu);
        const boundaryRect = measureLayoutBox(boundary);
        const availableHeight = boundaryRect.bottom - menuRect.top;
        dom.setStyle(menu, CHAT_MODEL_MENU_MAX_HEIGHT_PROPERTY, `${String(Math.max(0, availableHeight))}px`);
    }

    #syncOpenMenuSearch(root: HTMLElement, state: ChatModelControlRenderState): void {
        if (state.nextOpenMenu === null) {
            return;
        }
        const scope = requireChatModelControlScopeFromRoot(root);
        if (state.nextOpenMenu.scope !== scope) {
            return;
        }
        const menu = dom.resolve(CHAT_MODEL_OPEN_MENU_SELECTOR, root);
        if (!(menu instanceof HTMLElement)) {
            throw new Error('Chat model control menu search sync requires an open menu');
        }
        applyChatModelMenuSearchFilter(menu, state.menuSearchQuery);
    }

    #resolveInputWrapper(): HTMLElement | null {
        const candidate = this.#host.pageDom.query(CHAT_INPUT_WRAPPER_SELECTOR)[0] ?? null;
        return candidate instanceof HTMLElement ? candidate : null;
    }

    #requiresStructureRender(currentControl: HTMLElement, nextControl: HTMLElement | null): boolean {
        if (!(nextControl instanceof HTMLElement)) {
            throw new Error('Chat model control render output requires a single HTMLElement root');
        }
        return currentControl.classList.contains('chat-model-control--multi') !== nextControl.classList.contains('chat-model-control--multi');
    }

    #resolveTrigger(control: HTMLElement, slotIndex: number): HTMLElement | null {
        const selector = `.chat-model-control-primary[data-slot-index="${String(slotIndex)}"], .chat-model-slot[data-slot-index="${String(slotIndex)}"]`;
        const trigger = dom.resolve(selector, control);
        return trigger instanceof HTMLElement ? trigger : null;
    }

    isCurrentConversationExecuting(): boolean {
        const conversationId = this.#host.getCurrentConversation()?.id ?? null;
        const normalizedConversationId = normalizeConversationId(conversationId);
        return normalizedConversationId ? this.#host.isConversationExecuting(normalizedConversationId) : false;
    }
}

export { ChatModelControlRenderController };
export type { ChatModelControlRenderHost };
