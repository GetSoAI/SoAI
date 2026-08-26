/* SoAI - Power routed page [frontend/assets/ts/pages/power/PowerPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { releaseCollectionCardReveal, stageCollectionGridCardReveal } from '@core/collectionpage/cardReveal.ts';
import { optionalHTMLElement, optionalInput } from '@core/dom/narrowElement.ts';
import { POWER_OPERATIONS } from '@core/realtime/streammanager/resources/ids.ts';
import { getRestartState, subscribeRestartState } from '@core/restartStateService.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { isPowerActionId, type PowerActionId } from '@pages/power/actions.ts';
import { PAGE_ID, PAGE_MODULE_ID } from '@pages/power/contracts/constants.ts';
import { PowerPageActionService } from '@pages/power/controllers/page/actionService.ts';
import { PowerOperationLifecycle } from '@pages/power/controllers/powerOperationLifecycleController.ts';
import { focusPowerInitialAction } from '@pages/power/controllers/page/initialActionFocusController.ts';
import { confirmAndRunPowerAction, mapPowerViewActions, normalizePowerRestartState, refreshPowerRestartReminderUi, type PowerRestartNoticeTarget } from '@pages/power/controllers/page/powerPageSupport.ts';
import { requirePowerUi } from '@pages/power/dom.ts';
import type { ConfirmActionOptions, PowerActionEffects, PowerApi, PowerPageDependencies, PowerUi } from '@pages/power/types.ts';
import { renderPowerPageView } from '@pages/power/view.ts';

const CONTENT_SLOT_MARKER = '<!-- Page content goes here -->';
class PowerPage extends StaticBasePage {
    readonly #dependencies: PowerPageDependencies;
    #ui: PowerUi | null = null;
    #actionService: PowerPageActionService;
    readonly #operationLifecycle: PowerOperationLifecycle;
    readonly #restartStateSubscriptions: ResourceTracker = new ResourceTracker();
    constructor(dependencies: PowerPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#dependencies = dependencies;
        this.#actionService = new PowerPageActionService({
            getPowerApi: () => this.#requirePowerApi(),
            effects: this.#createEffects(),
            host: {
                getOptionId: (actionKey, optionParameter): string => this.#getOptionId(actionKey, String(optionParameter)),
                optionalOptionInput: (selectorOrId: string): HTMLInputElement | null => this.#optionalOptionInput(selectorOrId)
            },
            confirmAction: async (options: ConfirmActionOptions): Promise<boolean> =>
                confirmAndRunPowerAction(options, {
                    showNotification: (message: string, type: 'success'): void => this.feedback.show(message, type),
                    showErrorNotification: (message: string): void => this.feedback.show(message, 'error')
                })
        });
        this.#operationLifecycle = new PowerOperationLifecycle({
            api: () => this.#requirePowerApi(),
            countdownOverlay: this.#dependencies.countdownOverlay,
            restartOverlay: this.#dependencies.restartOverlay,
            powerOverlay: this.#dependencies.powerOverlay,
            subscribe: (resource, handler) => this.streaming.subscribeResourceValue(resource, handler),
            showFeedback: (message, type): void => this.feedback.show(message, type),
            setOperationActive: (active): void => this.#actionService.setOperationActive(active)
        });
    }
    override getRequiredResources(): string[] {
        return [POWER_OPERATIONS];
    }
    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        return {};
    }
    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        const actionDefinitions = this.#actionService.buildActionDefinitions();
        const viewActions = mapPowerViewActions(actionDefinitions);
        const view = renderPowerPageView(
            {
                getIconSync: (name: IconName, options?: IconOptions): TrustedHtml => this.services.getIconSync(name, options),
                getOptionId: (actionKey: string, parameter: string): string => this.#getOptionId(actionKey, parameter)
            },
            viewActions
        );
        const header = this.layout.generateHeader(view.header);
        if (!header.html.includes(CONTENT_SLOT_MARKER)) {
            throw new Error('Power page standard header is missing content slot marker');
        }
        return toTrustedUiHtml(header.html.replace(CONTENT_SLOT_MARKER, view.content));
    }
    override async initializeShell(_parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#ui = this.#resolvePowerUi();
        this.pageElements.enableCheckerboard(this.#ui.grid, '.ui-collection-card');
        this.#subscribeRestartState();
        this.#operationLifecycle.subscribe();
        this.#refreshRestartReminder();
    }
    bindPageEvents(): void {
        const ui = this.#requireUi();
        const signal = this.pageLifecycle.beginListeners();
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'PowerPage',
            isAction: isPowerActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    onAction: ({ action }): void => this.#handleClick(action)
                }
            }
        });
    }
    override async commitInitialContent(context: { signal?: AbortSignal } = {}): Promise<void> {
        const ui = this.#requireUi();
        stageCollectionGridCardReveal(ui.root, ui.grid, context.signal ?? null);
        await super.commitInitialContent(context);
    }
    override async afterPageReveal(context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterPageReveal(context);
        releaseCollectionCardReveal(this.#requireUi().root, context.signal ?? null);
        focusPowerInitialAction({ pageDom: this.pageDom, router: this.dependencies.router }, this.#requireUi().root);
    }
    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        this.#restartStateSubscriptions.cleanup();
        this.#operationLifecycle.cleanup();
        this.#ui = null;
    }
    #resolvePowerUi(): PowerUi {
        return requirePowerUi({
            requireHTMLElement: (selector, context) => this.pageDom.requireHTMLElement(selector, context),
            optionalHTMLElement: (selector, context) => this.pageDom.optionalHTMLElement(selector, context)
        });
    }
    #requireUi(): PowerUi {
        if (!this.#ui) {
            this.#ui = this.#resolvePowerUi();
        }
        return this.#ui;
    }
    #requirePowerApi(): PowerApi {
        const systemApi = this.dependencies.api.system;
        if (!isObject(systemApi)) {
            throw new Error('System API is unavailable for power actions');
        }
        const powerApi = systemApi['power'];
        if (!isObject(powerApi)) {
            throw new Error('Power API is unavailable for power actions');
        }
        const candidate = powerApi;
        if (!isFunction(candidate['restartApplication']) || !isFunction(candidate['shutdownApplication']) || !isFunction(candidate['shutdown']) || !isFunction(candidate['reboot']) || !isFunction(candidate['suspend']) || !isFunction(candidate['hibernate']) || !isFunction(candidate['active']) || !isFunction(candidate['get']) || !isFunction(candidate['cancel'])) {
            throw new Error('Power API is missing required methods');
        }
        return candidate;
    }
    #createEffects(): PowerActionEffects {
        return {
            operationAccepted: (response): void => this.#operationLifecycle.operationAccepted(response)
        };
    }
    #handleClick(action: PowerActionId): void {
        terminateHandledPromise(
            this.pageLifecycle.run(`power:action:${action}`, async (): Promise<void> => {
                await this.#actionService.executeAction(action);
                this.#refreshRestartReminder();
            })
        );
    }
    #getOptionId(actionKey: string, parameter: string): string {
        return `power-option-${actionKey}-${parameter}`;
    }
    #optionalOptionInput(selectorOrId: string): HTMLInputElement | null {
        return optionalInput(this.pageDom.optional(selectorOrId), `Power option "${selectorOrId}"`);
    }
    #subscribeRestartState(): void {
        this.#restartStateSubscriptions.cleanup();
        this.#restartStateSubscriptions.track(
            subscribeRestartState(() => {
                this.#refreshRestartReminder();
            })
        );
    }
    #refreshRestartReminder(): void {
        const ui = this.#ui;
        if (!ui || (!ui.applicationRestartNotice && !ui.systemRestartNotice)) {
            return;
        }
        const restartState = normalizePowerRestartState(getRestartState());
        refreshPowerRestartReminderUi(
            {
                application: this.#resolveRestartNoticeTarget(ui.applicationRestartNotice, ui.applicationRestartOptions),
                system: this.#resolveRestartNoticeTarget(ui.systemRestartNotice, ui.systemRestartOptions)
            },
            restartState,
            {
                updateText: (target: HTMLElement, text: string): void => this.pageDom.updateText(target, text),
                addHiddenClass: (target: HTMLElement): void => this.pageDom.addClass(target, 'u-hidden'),
                removeHiddenClass: (target: HTMLElement): void => this.pageDom.removeClass(target, 'u-hidden')
            }
        );
    }
    #resolveRestartNoticeTarget(notice: HTMLElement | null, options: HTMLElement | null): PowerRestartNoticeTarget {
        if (!notice) {
            return { notice: null, message: null, options };
        }
        const message = optionalHTMLElement(this.pageDom.optional('.power-restart-notice-message', notice), 'Power restart notice message');
        return { notice, message, options };
    }
}
export { PAGE_ID, PAGE_MODULE_ID, PowerPage };
