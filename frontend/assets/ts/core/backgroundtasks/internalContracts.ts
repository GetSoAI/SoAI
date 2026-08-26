/* SoAI - Shared background tasks internal contracts [frontend/assets/ts/core/backgroundtasks/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface BackgroundTasksRuntime {
    wallpaperContentCheckTimerId: ReturnType<typeof setTimeout> | null;
    solidBgContentCheckTimerId: ReturnType<typeof setTimeout> | null;
    wallpaperAnimationTimerId: ReturnType<typeof setTimeout> | null;
    solidBgAnimationTimerId: ReturnType<typeof setTimeout> | null;
    wallpaperUrl: string | null;
    wallpaperAvailable: boolean;
    solidBackgroundColor: string | null;
    solidBackgroundAvailable: boolean;
    initialized: boolean;
    animationShown: boolean;
    excludedRoutes: Set<string>;
    navigationUnsubscribe: (() => void) | null;
}

interface BackgroundTasksInitializationOptions {
    force?: boolean | undefined;
    signal?: AbortSignal | undefined;
}

export type { BackgroundTasksInitializationOptions, BackgroundTasksRuntime };
