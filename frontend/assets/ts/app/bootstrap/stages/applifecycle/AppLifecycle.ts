/* SoAI - Frontend application lifecycle ownership [frontend/assets/ts/app/bootstrap/stages/applifecycle/AppLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runAppLifecycleBootstrap } from '@app/bootstrap/stages/applifecycle/bootstrap.ts';
import { applyLifecycleBackground, destroyLifecycleRegisteredComponents, initializeLifecycleComponents, refreshLifecycleSoaiOsAccess } from '@app/bootstrap/stages/applifecycle/effects.ts';
import { renderLifecycleInitializationError, toggleMainUIVisibility } from '@app/bootstrap/stages/applifecycle/dom.ts';
import { LAYOUT_REGISTRY_SKIP } from '@app/bootstrap/stages/applifecycle/constants.ts';
import { runExclusiveLifecycleLogin } from '@app/bootstrap/stages/applifecycle/loginHandoff.ts';
import { resolveInitialRoute } from '@app/bootstrap/stages/applifecycle/routing.ts';
import { initializeLifecycleDataHubRuntime, monitorLifecycleConnectionRuntime, setupAuthenticatedLifecycleSession, setupLifecycleUiEventRuntime } from '@app/bootstrap/stages/applifecycle/runtime.ts';
import { LifecycleAuthSession, runAppLifecycleLogin, runAppLifecycleLogout } from '@app/bootstrap/stages/applifecycle/session.ts';
import type { AppLifecycleDependencies, LifecycleBackgroundOptions, LifecycleRoute } from '@app/bootstrap/stages/applifecycle/types.ts';
import { AUTH_ROUTE_WIZARD, resolveAuthenticatedRouteTarget } from '@core/routing/router/authRouteTarget.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

class AppLifecycle {
    readonly #dependencies: AppLifecycleDependencies;
    #dataHubInitialization: Promise<void> | null = null;
    #chartWarmupPromise: Promise<void> | null = null;
    #routerWarmupUnsubscribe: (() => void) | null = null;
    #navigationBootstrapUnsubscribe: (() => void) | null = null;
    #uiEventsBound = false;
    #uiTracker: ResourceTracker | null = null;
    #bootstrapInProgress = false;
    #authSession = new LifecycleAuthSession();
    connectionSubscription: (() => void) | null = null;
    dataHubConnectionSubscription: (() => void) | null = null;
    dataHubReady = false;
    bootstrapPromise: Promise<void> | null = null;
    isRefreshScenario = false;
    stateMeta: { initialized: boolean } = { initialized: false };
    chartWarmupRoutes: Set<string> = new Set(['hardware']);

    constructor(dependencies: AppLifecycleDependencies) {
        this.#dependencies = dependencies;
    }

    async bootstrap(): Promise<void> {
        const isRefresh = this.#dependencies.boot.getIsRefreshScenario();
        if (this.bootstrapPromise && !isRefresh) {
            return this.bootstrapPromise;
        }
        if (isRefresh) {
            this.bootstrapPromise = null;
        }
        this.bootstrapPromise = (async (): Promise<void> => {
            this.isRefreshScenario = isRefresh;
            this.#bootstrapInProgress = true;
            try {
                await runAppLifecycleBootstrap({
                    dependencies: this.#dependencies,
                    isRefreshScenario: this.isRefreshScenario,
                    navigationBootstrapUnsubscribe: this.#navigationBootstrapUnsubscribe,
                    connectionSubscription: this.connectionSubscription,
                    dataHubConnectionSubscription: this.dataHubConnectionSubscription,
                    routerWarmupUnsubscribe: this.#routerWarmupUnsubscribe,
                    uiTracker: this.#uiTracker,
                    setNavigationBootstrapUnsubscribe: (value) => {
                        this.#navigationBootstrapUnsubscribe = value;
                    },
                    setConnectionSubscription: (value) => {
                        this.connectionSubscription = value;
                    },
                    setDataHubConnectionSubscription: (value) => {
                        this.dataHubConnectionSubscription = value;
                    },
                    setRouterWarmupUnsubscribe: (value) => {
                        this.#routerWarmupUnsubscribe = value;
                    },
                    setUiTracker: (value) => {
                        this.#uiTracker = value;
                    },
                    setStateUninitialized: () => {
                        this.stateMeta.initialized = false;
                    },
                    resetUiBoundState: () => this.#resetSessionState(),
                    clearBootstrapPromise: () => {
                        this.bootstrapPromise = null;
                    },
                    registerAuthHandlers: () => this.registerAuthHandlers(),
                    releaseAuthHandlers: () => this.releaseAuthHandlers(),
                    refreshSoaiOsAccess: () => refreshLifecycleSoaiOsAccess(this.#dependencies.soaiOsCapabilities),
                    resolveInitialRoute: (isAuthenticated, needsWizard) => this.resolveInitialRoute(isAuthenticated, needsWizard),
                    setupAuthenticatedSession: (options) => this.setupAuthenticatedSession(options),
                    applyBackground: (route, options) => this.applyBackground(route, options),
                    monitorConnectionStatus: () => this.monitorConnectionStatus(),
                    toggleMainUI: (show) => this.toggleMainUI(show),
                    destroyRegisteredComponents: () => this.destroyRegisteredComponents(),
                    renderInitializationError: (error) => this.renderInitializationError(error)
                });
                this.stateMeta.initialized = true;
            } finally {
                this.#bootstrapInProgress = false;
            }
        })();
        return this.bootstrapPromise;
    }

    registerAuthHandlers(): void {
        this.#authSession.register({
            auth: this.#dependencies.auth,
            host: {
                isBootstrapInProgress: () => this.#bootstrapInProgress,
                handleLogin: () => this.handleLogin(),
                handleLogout: () => this.handleLogout()
            }
        });
    }

    releaseAuthHandlers(): void {
        this.#authSession.release();
    }

    async resolveInitialRoute(isAuthenticated: boolean, needsWizard: boolean): Promise<string> {
        return resolveInitialRoute({
            isAuthenticated,
            needsWizard,
            router: this.#dependencies.router,
            toggleMainUI: (show) => this.toggleMainUI(show),
            isWizardCompletionPending: () => this.#dependencies.storage.isWizardCompletionPending()
        });
    }

    async setupAuthenticatedSession(options: { force?: boolean | undefined; initialRoute?: string | null | undefined }): Promise<void> {
        await setupAuthenticatedLifecycleSession({
            dependencies: this.#dependencies,
            force: options.force,
            initialRoute: options.initialRoute,
            getCurrentWarmupPromise: () => this.#chartWarmupPromise,
            setCurrentWarmupPromise: (value) => {
                this.#chartWarmupPromise = value;
            },
            chartWarmupRoutes: this.chartWarmupRoutes,
            routerWarmupUnsubscribe: this.#routerWarmupUnsubscribe,
            setRouterWarmupUnsubscribe: (value) => {
                this.#routerWarmupUnsubscribe = value;
            },
            initializeDataHub: () => this.initializeDataHub(),
            initializeComponents: (runtimeOptions) => this.initializeComponents(runtimeOptions),
            setupEventListeners: () => this.setupEventListeners()
        });
    }

    async handleLogin(): Promise<void> {
        await runExclusiveLifecycleLogin(this, () =>
            runAppLifecycleLogin({
                dependencies: this.#dependencies,
                uiTracker: this.#uiTracker,
                setUiTracker: (value) => {
                    this.#uiTracker = value;
                },
                navigationBootstrapUnsubscribe: this.#navigationBootstrapUnsubscribe,
                setNavigationBootstrapUnsubscribe: (value) => {
                    this.#navigationBootstrapUnsubscribe = value;
                },
                connectionSubscription: this.connectionSubscription,
                setConnectionSubscription: (value) => {
                    this.connectionSubscription = value;
                },
                setStateUninitialized: () => {
                    this.stateMeta.initialized = false;
                },
                shouldStayOnAuthRoute: (routeKey) => routeKey === AUTH_ROUTE_WIZARD && this.#dependencies.storage.isWizardCompletionPending(),
                resolveAuthenticatedRoute: () => {
                    if (this.#dependencies.storage.isWizardCompletionPending()) {
                        return AUTH_ROUTE_WIZARD;
                    }
                    const redirectAfterLogin = this.#dependencies.storage.getRedirectAfterLogin();
                    const target = resolveAuthenticatedRouteTarget(this.#dependencies.router, {
                        currentRoute: this.#dependencies.router.getCurrentRoute() ?? this.#dependencies.router.getRouteFromHash(),
                        redirectAfterLogin
                    });
                    if (redirectAfterLogin && redirectAfterLogin === target) {
                        this.#dependencies.storage.clearRedirectAfterLogin();
                    }
                    return target;
                },
                navigateToAuthenticatedRoute: async (route) => {
                    await this.#dependencies.router.navigate(route, { force: true, replace: true });
                },
                monitorConnectionStatus: () => this.monitorConnectionStatus(),
                toggleMainUI: (show) => this.toggleMainUI(show),
                refreshSoaiOsAccess: () => refreshLifecycleSoaiOsAccess(this.#dependencies.soaiOsCapabilities),
                setupAuthenticatedSession: (options) => this.setupAuthenticatedSession(options),
                applyBackground: (route, options) => this.applyBackground(route, options)
            })
        );
    }

    async handleLogout(): Promise<void> {
        await runAppLifecycleLogout({
            dependencies: this.#dependencies,
            uiTracker: this.#uiTracker,
            setUiTracker: (value) => {
                this.#uiTracker = value;
            },
            navigationBootstrapUnsubscribe: this.#navigationBootstrapUnsubscribe,
            setNavigationBootstrapUnsubscribe: (value) => {
                this.#navigationBootstrapUnsubscribe = value;
            },
            connectionSubscription: this.connectionSubscription,
            setConnectionSubscription: (value) => {
                this.connectionSubscription = value;
            },
            dataHubConnectionSubscription: this.dataHubConnectionSubscription,
            setDataHubConnectionSubscription: (value) => {
                this.dataHubConnectionSubscription = value;
            },
            routerWarmupUnsubscribe: this.#routerWarmupUnsubscribe,
            setRouterWarmupUnsubscribe: (value) => {
                this.#routerWarmupUnsubscribe = value;
            },
            resetLifecycleState: () => {
                this.stateMeta.initialized = false;
                this.#resetSessionState();
            },
            destroyRegisteredComponents: () => this.destroyRegisteredComponents(),
            toggleMainUI: (show) => this.toggleMainUI(show)
        });
    }

    async destroyRegisteredComponents(): Promise<void> {
        await destroyLifecycleRegisteredComponents(this.#dependencies.layoutShell, this.#dependencies.componentRegistry, this.#dependencies.router);
    }

    async initializeComponents(options: { force?: boolean | undefined } = {}): Promise<void> {
        await initializeLifecycleComponents({
            layoutShell: this.#dependencies.layoutShell,
            componentRegistry: this.#dependencies.componentRegistry,
            skippedComponents: LAYOUT_REGISTRY_SKIP,
            force: options.force
        });
    }

    async initializeDataHub(): Promise<void> {
        const dataHubState = await initializeLifecycleDataHubRuntime(this.#dependencies, {
            initialization: this.#dataHubInitialization,
            ready: this.dataHubReady,
            connectionSubscription: this.dataHubConnectionSubscription
        });
        this.#dataHubInitialization = dataHubState.initialization;
        this.dataHubReady = dataHubState.ready;
        this.dataHubConnectionSubscription = dataHubState.connectionSubscription;
    }

    setupEventListeners(): void {
        const uiEventState = setupLifecycleUiEventRuntime(this.#dependencies, this.#uiEventsBound, this.#uiTracker);
        this.#uiEventsBound = uiEventState.uiEventsBound;
        this.#uiTracker = uiEventState.uiTracker;
    }

    monitorConnectionStatus(): void {
        if (this.connectionSubscription) {
            return;
        }
        const unsubscribe = monitorLifecycleConnectionRuntime(this.#dependencies, this.connectionSubscription);
        if (!unsubscribe) {
            return;
        }
        this.connectionSubscription = () => {
            unsubscribe();
            this.connectionSubscription = null;
        };
    }

    async applyBackground(route: LifecycleRoute, options: LifecycleBackgroundOptions = {}): Promise<void> {
        await applyLifecycleBackground(this.#dependencies.backgroundTasks, this.isRefreshScenario, route, options);
    }

    toggleMainUI(show: boolean): void {
        toggleMainUIVisibility(show, this.#dependencies.state);
    }

    renderInitializationError(error: Error): void {
        renderLifecycleInitializationError(error, this.#dependencies.boot.finalizePreloader);
    }

    #resetSessionState(): void {
        this.#uiEventsBound = false;
        this.#dataHubInitialization = null;
        this.dataHubReady = false;
        this.#chartWarmupPromise = null;
    }
}

export { AppLifecycle };
export type { AppLifecycleDependencies };
