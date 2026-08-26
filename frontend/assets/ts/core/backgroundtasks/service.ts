/* SoAI - Shared background tasks service [frontend/assets/ts/core/backgroundtasks/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { EXCLUDED_ROUTES } from '@core/backgroundtasks/constants.ts';
import { applyBackgroundRoute, clearAllTimers, disableBackground, initializeBackgroundTasks, refreshBackgroundTasks } from '@core/backgroundtasks/actions.ts';
import { clearBackgroundClasses, removeWallpaperStyles, requireBody } from '@core/backgroundtasks/effects.ts';
import type { BackgroundTasksInitializationOptions, BackgroundTasksRuntime } from '@core/backgroundtasks/internalContracts.ts';
import type { BackgroundRoute } from '@core/backgroundtasks/types.ts';

interface BackgroundTasksService {
    initialize: (options?: BackgroundTasksInitializationOptions) => Promise<void>;
    applyForRoute: (route: BackgroundRoute) => void;
    refresh: () => Promise<void>;
    reset: () => void;
}

const createBackgroundTasksRuntime = (): BackgroundTasksRuntime => ({
    wallpaperContentCheckTimerId: null,
    solidBgContentCheckTimerId: null,
    wallpaperAnimationTimerId: null,
    solidBgAnimationTimerId: null,
    wallpaperUrl: null,
    wallpaperAvailable: false,
    solidBackgroundColor: null,
    solidBackgroundAvailable: false,
    initialized: false,
    animationShown: false,
    excludedRoutes: new Set(EXCLUDED_ROUTES),
    navigationUnsubscribe: null
});

class BackgroundTasks implements BackgroundTasksService {
    #runtime: BackgroundTasksRuntime;
    #initialization: Promise<void> | null = null;
    #initializationController: AbortController | null = null;
    #refreshQueue: Promise<void> = Promise.resolve();
    #route: BackgroundRoute | undefined;

    constructor() {
        this.#runtime = createBackgroundTasksRuntime();
    }

    initialize(options: BackgroundTasksInitializationOptions = {}): Promise<void> {
        if (this.#runtime.initialized && options.force !== true) {
            return Promise.resolve();
        }
        if (this.#initialization && options.force !== true) {
            return this.#initialization;
        }
        this.#initializationController?.abort('background-reinitialize');
        const controller = new AbortController();
        this.#initializationController = controller;
        let task: Promise<void> | null = null;
        task = initializeBackgroundTasks(this.#runtime, { ...options, signal: controller.signal })
            .then(() => {
                if (!controller.signal.aborted) {
                    applyBackgroundRoute(this.#runtime, this.#route);
                }
            })
            .finally(() => {
                if (this.#initialization === task) {
                    this.#initialization = null;
                }
                if (this.#initializationController === controller) {
                    this.#initializationController = null;
                }
            });
        this.#initialization = task;
        return task;
    }

    applyForRoute(route: BackgroundRoute): void {
        this.#route = route;
        if (this.#runtime.initialized) {
            applyBackgroundRoute(this.#runtime, route);
        }
    }

    refresh(): Promise<void> {
        const refreshTask = this.#refreshQueue.then(async () => {
            await refreshBackgroundTasks(this.#runtime);
        });
        this.#refreshQueue = refreshTask.then(
            () => undefined,
            () => undefined
        );
        return refreshTask;
    }

    reset(): void {
        this.#initializationController?.abort('background-reset');
        this.#initializationController = null;
        this.#initialization = null;
        this.#route = undefined;
        if (this.#runtime.navigationUnsubscribe) {
            this.#runtime.navigationUnsubscribe();
        }
        this.#runtime.navigationUnsubscribe = null;
        this.#runtime.initialized = false;
        this.#runtime.animationShown = false;
        this.#runtime.excludedRoutes = new Set(EXCLUDED_ROUTES);
        clearAllTimers(this.#runtime);
        clearBackgroundClasses(requireBody());
        removeWallpaperStyles();
        disableBackground(this.#runtime);
    }
}

let backgroundTasksInstance: BackgroundTasks | null = null;

const getBackgroundTasks = (): BackgroundTasksService => {
    if (!backgroundTasksInstance) {
        backgroundTasksInstance = new BackgroundTasks();
    }
    return backgroundTasksInstance;
};

const resetBackgroundTasksInstance = (): void => {
    if (backgroundTasksInstance) {
        backgroundTasksInstance.reset();
        backgroundTasksInstance = null;
    }
};

export { getBackgroundTasks, resetBackgroundTasksInstance };
