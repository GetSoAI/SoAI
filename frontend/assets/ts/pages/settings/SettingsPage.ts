/* SoAI - Settings routed page [frontend/assets/ts/pages/settings/SettingsPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { destroyFormManager } from '@core/formService.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import type { SaveController } from '@core/save/public.ts';
import { resolveSettingsConfigPathFromQuery } from '@core/settings/configPathDeepLink.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { composeNormalTabDefinitions, PAGE_ID, PAGE_MODULE_ID } from '@features/settings/public.ts';
import { isSettingsActionId } from '@pages/settings/actions.ts';
import { isSettingsNormalTabVisibleById, refreshAccessState } from '@pages/settings/controllers/page/settingsAccessController.ts';
import type { SettingsPageDependencies, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { disposeManagers, loadData, resetElementCache, setupManagersEventListeners } from '@pages/settings/controllers/page/service.ts';
import { SettingsDirtyStateManager } from '@pages/settings/controllers/page/SettingsDirtyStateManager.ts';
import { SettingsSaveController } from '@pages/settings/controllers/page/SettingsSaveController.ts';
import { createInitialSettingsPageState, type SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { InitialReloadsController } from '@pages/settings/controllers/page/reload/InitialReloadsController.ts';
import { handleSettingsInitialModal } from '@pages/settings/controllers/page/initialModal.ts';
import { applyAdvancedModeChange, applyConfigPathDeepLink, onTabChange, renderView, setupNavigationGuard, setupSearch } from '@pages/settings/controllers/page/view.ts';
import { SettingsPageOperationsController } from '@pages/settings/controllers/page/SettingsPageOperationsController.ts';
import { createSettingsActionHandlers } from '@pages/settings/controllers/settingsActionHandlers.ts';
import { requireSettingsUi } from '@pages/settings/dom.ts';
import type { SettingsUi } from '@pages/settings/types.ts';

class SettingsPage extends StaticBasePage {
    searchQuery = '';
    #state: SettingsPageState;
    readonly #runtime: SettingsRuntimeContext;
    readonly #save: SaveController;
    readonly #operations: SettingsPageOperationsController;
    #hasPreparedAccessSnapshot = false;

    constructor({ restartOverlay, product, dashboardTitle }: SettingsPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.layout.configure({ onTabChange: (newTab) => this.#onTabChange(newTab) });
        if (!restartOverlay || !isFunction(restartOverlay.show)) {
            throw new Error('SettingsPage requires a restart overlay service dependency');
        }
        this.#state = createInitialSettingsPageState(restartOverlay);
        this.#state.dirtyStateManager = new SettingsDirtyStateManager({ pageDom: this.pageDom, getData: (element, key) => this.dependencies.dom.getData(element, key) }, this.#state);
        this.#runtime = {
            edition: {
                product,
                dashboardTitle,
                normalTabs: composeNormalTabDefinitions(product?.tabs)
            },
            owners: {
                layout: this.layout,
                streaming: this.streaming,
                services: this.services,
                pageElements: this.pageElements,
                pageLifecycle: this.pageLifecycle,
                pageDom: this.pageDom,
                pageResources: this.pageResources,
                feedback: this.feedback,
                api: this.dependencies.api,
                auth: this.dependencies.auth,
                languageService: this.dependencies.languageService,
                storage: this.dependencies.storage,
                router: this.dependencies.router,
                dom: this.dependencies.dom,
                pageContext: this.pageContext
            },
            controls: {
                getSearchQuery: () => this.searchQuery,
                setSearchQuery: (value) => {
                    this.searchQuery = value;
                },
                isDestroyed: () => this.isDestroyed
            }
        };
        this.#save = SettingsSaveController(this.#runtime, this.#state);
        this.#operations = new SettingsPageOperationsController(this.#runtime, this.#state, this.#save);
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        await refreshAccessState(this.#runtime, this.#state);
        this.#hasPreparedAccessSnapshot = true;
        let advancedMode = this.dependencies.storage.getAdvancedMode();
        if (!this.#state.advancedAccessEnabled) {
            advancedMode = false;
        } else if (resolveSettingsConfigPathFromQuery(parameters) !== null) {
            advancedMode = true;
        }
        this.#state.advancedMode = advancedMode;
        return { advancedMode };
    }

    override async renderView(context?: RenderContext): Promise<TrustedHtml> {
        return renderView(this.#runtime, this.#state, context);
    }

    override async initializeShell(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.initializeShell(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        setupSearch(this.#runtime, this.#state);
        setupNavigationGuard(this.#runtime, this.#state, () => this.#save.hasChanges());
    }

    bindPageEvents(): void {
        const signal = this.pageLifecycle.beginListeners();
        const ui = this.#ensureUi();
        const refreshOcr = (): void => {
            terminateHandledPromise(
                this.pageLifecycle.run('settings:refreshOcr', async () => {
                    await this.#state.preferencesManager?.refreshOcrPreference();
                })
            );
        };
        this.pageResources.on(window, 'focus', refreshOcr, { signal });
        this.#save.attach({ resolveSaveButtons: () => this.#resolveSaveButtons(ui), autoNotifyRoot: ui.root });

        const handlers = createSettingsActionHandlers({
            refreshOcr,
            save: (): void => {
                terminateHandledPromise(this.#save.requestSave());
            },
            toggleAdvancedMode: (event: Event, element: HTMLElement): void => {
                if (!this.#state.advancedAccessEnabled) {
                    return;
                }
                if (event.type !== 'click' || element !== ui.advancedModeToggleButton) {
                    return;
                }

                this.#state.advancedMode = !this.#state.advancedMode;
                applyAdvancedModeChange(this.#runtime, this.#state);
            }
        });

        bindPageActionDispatcher({
            root: ui.pageActionRoot,
            signal,
            label: 'SettingsPage',
            isAction: isSettingsActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'interactive',
                    ignorePrevented: true,
                    onAction: ({ event, action, actionElement }): void => {
                        handlers[action](event, actionElement);
                    }
                },
                change: {
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }): void => {
                        handlers[action](event, actionElement);
                    }
                }
            }
        });
        setupManagersEventListeners(this.#runtime, this.#state);
    }

    #onTabChange(newTab: string): void {
        onTabChange(this.#runtime, this.#state, newTab);
    }

    override async prepareInitialContent(parameters?: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        this.#state.initialRouteParameters = parameters ?? null;
        const refreshAccess = !this.#hasPreparedAccessSnapshot;
        this.#hasPreparedAccessSnapshot = false;
        await loadData(this.#runtime, this.#state, this.#operations, { signal: context.signal ?? null, refreshAccess });
        await handleSettingsInitialModal({ router: this.dependencies.router }, isSettingsNormalTabVisibleById(this.#runtime, this.#state, 'mcp') ? this.#state.mcpManager : null);
    }

    override async afterPageReveal(context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterPageReveal(context);
        applyConfigPathDeepLink(this.#runtime, this.#state);
        const timerId = this.pageResources.setTimer(() => InitialReloadsController(this.#runtime, this.#state, context.signal ?? null), 0);
        if (timerId === null) {
            throw new Error('Settings initial reload timer allocation failed');
        }
    }

    protected override beforePageRefreshCleanup(): void {
        disposeManagers(this.#state);
    }

    override async onRefresh(parameters?: JsonObject | null): Promise<void> {
        await super.onRefresh(parameters);
        this.#state.navigationGuardCleanup?.();
        this.#state.navigationGuardCleanup = null;
        setupNavigationGuard(this.#runtime, this.#state, () => this.#save.hasChanges());
    }

    override async onDestroy(): Promise<void> {
        this.#state.navigationGuardCleanup?.();
        this.#state.navigationGuardCleanup = null;
        this.pageLifecycle.abortListeners('settings-destroy');
        this.#save.dispose();
        this.#state.ui = null;
        disposeManagers(this.#state);
        this.#state.backupOperation = null;
        this.#state.backupListLoadStatus = 'idle';
        this.#state.configManager = null;
        this.#state.uiPrefsManager = null;
        resetElementCache(this.#state);
        this.#state.dirtyStateManager?.clearAll();
        this.#state.dirtyStateManager = null;
        this.#state.advancedRenderer = null;
        this.#state.advancedStructure = null;
        this.#state.advancedTabs = [];
        this.#state.settingsSearchHost = null;
        this.#state.initialRouteParameters = null;
        destroyFormManager('settings-content');
    }

    protected override onCancel(_reason: string): void {
        this.#hasPreparedAccessSnapshot = false;
        disposeManagers(this.#state);
    }

    #ensureUi(): SettingsUi {
        if (this.#state.ui) {
            return this.#state.ui;
        }
        this.#state.ui = requireSettingsUi({
            requireHTMLElement: (selector: string, context?: ParentNode): HTMLElement => {
                if (context && context instanceof Element) {
                    return this.pageDom.requireHTMLElement(selector, context);
                }
                return this.pageDom.requireHTMLElement(selector);
            },
            optionalHTMLElement: (selector: string, context?: ParentNode): HTMLElement | null => {
                if (context && context instanceof Element) {
                    return this.pageDom.optionalHTMLElement(selector, context);
                }
                return this.pageDom.optionalHTMLElement(selector);
            }
        });
        return this.#state.ui;
    }

    #resolveSaveButtons(ui: SettingsUi): HTMLButtonElement[] {
        return [ui.saveButton];
    }
}
export { SettingsPage, PAGE_ID, PAGE_MODULE_ID };
