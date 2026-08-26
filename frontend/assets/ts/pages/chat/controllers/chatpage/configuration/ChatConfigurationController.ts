/* SoAI - Chat configuration modal session ownership [frontend/assets/ts/pages/chat/controllers/chatpage/configuration/ChatConfigurationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { getEventHub } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { bindAvatarUploadEvents, bindChatConfigurationModalParameterEvents, CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID, CHAT_MEMORY_UPDATED_EVENT, CHAT_SELECTORS, isManagedConfigurationTabHidden, openChatToolCallOutputModal, resolveChatConfigurationTabId, type ChatConfigurationModalBindingsHost } from '@features/chat/public.ts';
import { isConversationAuthorityLocked } from '@core/chat/conversationAuthorityLock.ts';
import { isChatActionId, isChatHostedActionId } from '@pages/chat/actions.ts';
import { beginChatConfigurationModalOpen, invalidateChatConfigurationModalOpen } from '@pages/chat/controllers/chatConfigurationModalOpenController.ts';
import { createChatConfigurationTabsHost } from '@pages/chat/controllers/chatConfigurationTabsHostController.ts';
import { dispatchResolvedActionCandidate } from '@pages/chat/controllers/page/events/dispatch.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { disposeChatConfigurationTabs, type ChatConfigurationTabsHost } from '@pages/chat/widgets/chatconfigurationtabs/ChatConfigurationTabsController.ts';
import { refreshChatMemoryTab, type ChatMemoryTabHost } from '@pages/chat/widgets/memorytab/service.ts';
import { ChatPresetLibraryController } from '@pages/chat/controllers/chatconfigurationcontroller/ChatPresetLibraryController.ts';
import { ChatPresetSectionAdapterRegistry } from '@pages/chat/controllers/chatconfigurationcontroller/adapters.ts';
import { bindChatConfigurationInputs, routeConfigurationModelControlAction } from '@pages/chat/controllers/chatpage/configuration/events.ts';
import { attachChatConfigurationCloseGuards } from '@pages/chat/controllers/chatpage/configuration/guards.ts';
import type { ChatConfigurationDependencies } from '@pages/chat/controllers/chatpage/configuration/contracts.ts';

class ChatConfigurationController {
    readonly #page: ChatConfigurationDependencies;
    #inputDisposer: (() => void) | null = null;
    #tabsHost: ChatConfigurationTabsHost | null = null;
    #presetLibrary: ChatPresetLibraryController | null = null;
    #sessionAbort: AbortController | null = null;

    constructor(page: ChatConfigurationDependencies) {
        this.#page = page;
    }

    dispose(): void {
        this.#resetSessionState();
        this.#presetLibrary?.dispose();
        this.#presetLibrary = null;
        this.#tabsHost = null;
    }

    bindEvents(rootElement: HTMLElement, signal: AbortSignal, getRootEventsHost: () => ChatRootEventsHost | null): void {
        this.#resetSessionState();
        this.#bindModalEvents(signal, getRootEventsHost);
        bindAvatarUploadEvents(this.#createModalBindingsHost(), { inputsRoot: rootElement, resolvePreviewRoot: () => this.#resolveOpenConfigurationModal() }, signal);
        const handleMemoryUpdated = (): void => this.#refreshMemoryTabInBackground('Unexpected refreshMemoryTab rejection after chat memory update event');
        getEventHub().addEventListener(CHAT_MEMORY_UPDATED_EVENT, handleMemoryUpdated, { signal });
    }

    openMemoryProfile(): void {
        void this.#page.runtimeServices.firstRunModals.open('chatMemoryProfile', 'manual').catch((error): void => {
            errorHandler.error('ChatPage', 'Failed to open chat memory profile modal', ensureError(error));
            this.#page.feedback.show(i18n.t('chat.configuration.notifications.loadFailed'), 'error');
        });
    }

    openTab(tabId: string): void {
        const requestedTabId = resolveChatConfigurationTabId(tabId);
        const normalizedTabId = isConversationAuthorityLocked(this.#page.conversationView.current()) && isManagedConfigurationTabHidden(requestedTabId) ? 'general' : requestedTabId;
        const presenter = requireModalPresenter();
        if (presenter.isOpen(CHAT_CONFIGURATION_MODAL_ID)) {
            const tabs = this.#page.layout.getTabs();
            if (tabs) {
                this.#requireTabsHost().setActiveTab(normalizedTabId);
                return;
            }
            presenter.close(CHAT_CONFIGURATION_MODAL_ID);
        }
        this.#page.configurationRuntime.requireConfiguration().setActiveTab(normalizedTabId);
        this.#page.composerSurface.requireUi().toggleConfiguration(true);
    }

    async openToolCallOutput(inputArguments: { conversationId: string; callId: string; assistantTurnTimestamp: number; modelVariantIndex: number }): Promise<void> {
        await openChatToolCallOutputModal(
            {
                runWithBoundary: (name, task) => this.#page.pageLifecycle.run(name, task),
                hasClipboardSupport: () => this.#page.services.hasClipboardSupport(),
                copyToClipboard: (text, options) => this.#page.services.copyToClipboard(text, options),
                showNotification: (message, type) => this.#page.feedback.show(message, type)
            },
            inputArguments
        );
    }

    async refreshMemoryTab(): Promise<boolean> {
        const presenter = requireModalPresenter();
        if (!presenter.isOpen(CHAT_CONFIGURATION_MODAL_ID)) {
            return false;
        }
        const modal = presenter.requireElement(CHAT_CONFIGURATION_MODAL_ID);
        const token = this.#page.taskScope.concurrency.beginRenderSequence('memory-tab-refresh');
        const isStale = (): boolean => !this.#page.taskScope.concurrency.isRenderSequenceCurrent('memory-tab-refresh', token) || !presenter.isOpen(CHAT_CONFIGURATION_MODAL_ID) || presenter.requireElement(CHAT_CONFIGURATION_MODAL_ID) !== modal;
        const host: ChatMemoryTabHost = {
            pageDom: this.#page.pageDom,
            isCurrent: () => !isStale(),
            api: this.#page.api
        };
        try {
            await refreshChatMemoryTab(host, modal);
            return !isStale();
        } catch (error) {
            if (isStale()) return false;
            errorHandler.error('ChatPage', 'Failed to refresh chat memory tab', ensureError(error));
            this.#page.feedback.show(i18n.t('chat.configuration.notifications.loadFailed'), 'error');
            return false;
        }
    }

    async refreshMemoryTabFromAction(): Promise<void> {
        if (await this.refreshMemoryTab()) {
            this.#page.feedback.show(i18n.t('common.notifications.refreshCompleted'), 'refresh');
        }
    }

    handleModelAction(actionElement: HTMLElement): void {
        this.#page.taskScope.run('chat:configurationModelControl', async () => {
            await this.#page.configurationRuntime.requireConfiguration().modelControl.handleAction(actionElement);
        });
    }

    refreshPresets(): void {
        this.#requirePresetLibrary().refresh();
    }

    resetPresets(): void {
        this.#requirePresetLibrary().resetLibrary();
    }
    newPreset(): void {
        this.#requirePresetLibrary().newPreset();
    }

    applyPreset(actionElement: HTMLElement): void {
        this.#requirePresetLibrary().applyPreset(actionElement);
    }

    replacePreset(actionElement: HTMLElement): void {
        this.#requirePresetLibrary().editPreset(actionElement, 'replace');
    }

    renamePreset(actionElement: HTMLElement): void {
        this.#requirePresetLibrary().editPreset(actionElement, 'rename');
    }

    removePreset(actionElement: HTMLElement): void {
        this.#requirePresetLibrary().removePreset(actionElement);
    }

    submitPresetEditor(): void {
        this.#requirePresetLibrary().submitEditor();
    }

    cancelPresetEditor(): void {
        this.#requirePresetLibrary().cancelEditor();
    }

    reviewPresetEditor(): void {
        this.#requirePresetLibrary().reviewEditor();
    }

    #bindModalEvents(signal: AbortSignal, getRootEventsHost: () => ChatRootEventsHost | null): void {
        const bindModal = (modalId: string, onOpen: (modal: HTMLElement) => void, onClose: () => void, requireInitialActions: boolean): void => {
            const modal = requireModalPresenter().requireElement(modalId);
            if (modalId === CHAT_CONFIGURATION_MODAL_ID) {
                const configuration = this.#page.configurationRuntime.requireConfiguration();
                attachChatConfigurationCloseGuards({ modal, configuration, hasPresetDraft: () => this.#presetLibrary?.hasOpenEditor() === true, signal });
            }
            const handleModalOpen = (): void => onOpen(modal);
            modal.addEventListener('core.modal.open', handleModalOpen, { signal });
            modal.addEventListener('core.modal.close', onClose, { signal });
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
                            if (routeConfigurationModelControlAction({ action, actionElement, event, handle: () => this.handleModelAction(actionElement) })) {
                                return;
                            }
                            const host = getRootEventsHost();
                            if (host && isChatActionId(action) && !(actionElement instanceof HTMLInputElement) && !(actionElement instanceof HTMLSelectElement) && !(actionElement instanceof HTMLTextAreaElement)) dispatchResolvedActionCandidate(host, event, { action, actionElement });
                        }
                    }
                }
            });
        };
        bindModal(
            CHAT_CONFIGURATION_MODAL_ID,
            (modal) => this.#open(modal),
            () => this.#close(),
            true
        );
        bindModal(
            CHAT_MCP_DEFAULT_TOOLS_MODAL_ID,
            () => this.#setDefaultToolsExpanded(true),
            () => this.#setDefaultToolsExpanded(false),
            false
        );
    }

    #open(modal: HTMLElement): void {
        const bindings = this.#createModalBindingsHost();
        this.#resetSessionState();
        this.#inputDisposer = bindChatConfigurationModalParameterEvents(bindings, modal);
        this.#setConfigurationToggleActive(true);
        this.#page.configurationRuntime.requireConfiguration().beginConfigurationEdit();
        const sessionAbort = new AbortController();
        this.#sessionAbort = sessionAbort;
        bindChatConfigurationInputs(
            {
                handleModelSearchInput: (input) => this.#page.configurationRuntime.requireConfiguration().modelControl.handleSearchInput(input),
                closeModelMenu: () => this.#page.configurationRuntime.requireConfiguration().modelControl.closeMenu(),
                updatePresetSearch: (value) => this.#requirePresetLibrary().updateSearch(value),
                updatePresetName: (value) => this.#requirePresetLibrary().updateEditorName(value),
                updatePresetSection: (sectionId, selected) => this.#requirePresetLibrary().updateEditorSection(sectionId, selected)
            },
            modal,
            sessionAbort.signal
        );
        beginChatConfigurationModalOpen({
            host: this.#page,
            tabsHost: this.#requireTabsHost(),
            modalBindingsHost: bindings,
            modal,
            onTabsReady: () => {
                this.#page.configurationRuntime.requireConversationSettings().handleConfigurationOpen();
                this.#page.modelSession.updateUi(modal);
                this.#requirePresetLibrary().open(sessionAbort.signal);
            }
        });
    }

    #close(): void {
        invalidateChatConfigurationModalOpen(this.#page);
        this.#resetSessionState();
        const presenter = requireModalPresenter();
        if (presenter.isOpen(CHAT_MCP_DEFAULT_TOOLS_MODAL_ID)) presenter.close(CHAT_MCP_DEFAULT_TOOLS_MODAL_ID);
        disposeChatConfigurationTabs(this.#requireTabsHost());
        this.#page.configurationRuntime.requireConfiguration().cancelConfigurationEdit();
        this.#setConfigurationToggleActive(false);
        this.#page.configurationRuntime.requireConfiguration().hideHeaderSaveAction();
        this.#page.configurationRuntime.optionalConversationSettings()?.handleConfigurationClose?.();
    }

    #createModalBindingsHost(): ChatConfigurationModalBindingsHost {
        return {
            runUiTask: (operationId, task) => this.#page.taskScope.run(operationId, task),
            applyParameterValueFromElement: (element) => this.#page.composer.applyParameterValueFromElement(element),
            optionalHTMLElement: (selector, context) => {
                const element = dom.resolve(selector, context);
                return element instanceof HTMLElement ? element : null;
            },
            invalidateChatMarkup: (scope) => this.#page.conversationView.invalidate(scope),
            renderCurrentConversation: () => this.#page.conversationView.renderCurrent(),
            showNotification: (message, type) => this.#page.feedback.show(message, type),
            updateText: (target, text) => this.#page.pageDom.updateText(target, text),
            avatarStorage: this.#page.settings.storage,
            getAssistantAvatarIconHtml: () => this.#page.presentation.cachedIcon('model-default', { size: 18, strokeWidth: 1.5 }),
            getUserAvatarIconHtml: () => this.#page.presentation.cachedIcon('user', { size: 18, strokeWidth: 1.5 })
        };
    }

    #requireTabsHost(): ChatConfigurationTabsHost {
        if (!this.#tabsHost) {
            this.#tabsHost = createChatConfigurationTabsHost({
                page: { ...this.#page, layout: this.#page.layout, pageDom: this.#page.pageDom, getConversationSettingsManager: () => this.#page.configurationRuntime.optionalConversationSettings() },
                refreshMemoryTabInBackground: (message) => this.#refreshMemoryTabInBackground(message),
                onTabChange: (tabId) => {
                    if (tabId === 'presets') this.#presetLibrary?.enterTab();
                }
            });
        }
        return this.#tabsHost;
    }

    #refreshMemoryTabInBackground(message: string): void {
        void this.refreshMemoryTab().catch((error): void => errorHandler.error('ChatPage', message, ensureError(error)));
    }

    #resetSessionState(): void {
        this.#sessionAbort?.abort();
        this.#sessionAbort = null;
        this.#presetLibrary?.close();
        this.#inputDisposer?.();
        this.#inputDisposer = null;
        this.#page.taskScope.concurrency.beginRenderSequence('memory-tab-refresh');
    }

    #requirePresetLibrary(): ChatPresetLibraryController {
        if (!this.#presetLibrary) {
            const configuration = this.#page.configurationRuntime.requireConfiguration();
            const settings = this.#page.configurationRuntime.requireConversationSettings();
            this.#presetLibrary = new ChatPresetLibraryController({
                root: requireModalPresenter().requireElement(CHAT_CONFIGURATION_MODAL_ID),
                api: this.#page.api.webui.chat.presets,
                configuration: new ChatPresetSectionAdapterRegistry(configuration, settings),
                acquireOperation: () => configuration.operationGate().acquire('preset'),
                isOperationPending: () => configuration.operationGate().activeOperation() !== null,
                subscribeOperation: (listener) => configuration.operationGate().subscribe(listener),
                runTask: (operationId, task) => this.#page.taskScope.runResult(operationId, task),
                show: (message, type) => this.#page.feedback.show(message, type)
            });
        }
        return this.#presetLibrary;
    }

    #setConfigurationToggleActive(active: boolean): void {
        for (const element of this.#page.pageDom.query(CHAT_SELECTORS.CONFIGURATION_TOGGLE)) if (element instanceof HTMLElement) element.classList.toggle('is-active', active);
    }

    #setDefaultToolsExpanded(expanded: boolean): void {
        const trigger = dom.resolve(CHAT_SELECTORS.MCP_DEFAULT_TOOLS_TRIGGER, requireModalPresenter().requireElement(CHAT_CONFIGURATION_MODAL_ID));
        if (!(trigger instanceof HTMLElement)) throw new Error(`Chat configuration modal missing required element: ${CHAT_SELECTORS.MCP_DEFAULT_TOOLS_TRIGGER}`);
        trigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        if (expanded) this.#page.configurationRuntime.optionalConversationSettings()?.handleMcpDefaultToolsModalOpen?.();
    }

    #resolveOpenConfigurationModal(): HTMLElement | null {
        const presenter = requireModalPresenter();
        return presenter.isOpen(CHAT_CONFIGURATION_MODAL_ID) ? presenter.requireElement(CHAT_CONFIGURATION_MODAL_ID) : null;
    }
}

export { ChatConfigurationController };
export type { ChatConfigurationDependencies };
