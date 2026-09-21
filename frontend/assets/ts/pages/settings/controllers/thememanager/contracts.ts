/* SoAI - Settings page theme manager contracts [frontend/assets/ts/pages/settings/controllers/thememanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ToggleLabelState } from '@core/toggleSwitch.ts';
import type { WallpaperDownloadResponse, WallpaperInfoResponse, WallpaperUploadResponse } from '@core/api/contracts/wallpaperContracts.ts';
import type { StorageService } from '@features/settings/public.ts';
import type { WallpaperMetadata } from '@core/settings/contracts.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';

interface ThemeManagerDependencies {
    host: ThemeManagerHost;
    canManageSolidBackground: boolean;
    getGrantedActions: () => ReadonlySet<string>;
    dashboardProductTitle: () => (() => string) | null;
    updatePreferenceToggleLabel: (element: Element, enabled?: boolean) => void;
}

interface ThemeManagerHost extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    canManageWallpaper: () => boolean;
    uploadWallpaper: (file: File) => Promise<WallpaperUploadResponse>;
    downloadWallpaper: (url: string) => Promise<WallpaperDownloadResponse>;
    deleteWallpaper: () => Promise<void>;
    getWallpaperStatus: () => Promise<WallpaperInfoResponse>;
    storage: StorageService;
    getUiPrefValue: (key: UiPreferenceKey) => JsonValue | null | undefined;
    setUiPrefValue: (key: UiPreferenceKey, value: JsonValue | null | undefined) => void;
    runWithBoundary: <T>(name: string, task: () => Promise<T> | T) => Promise<T>;
    getCurrentWallpaperUrl: () => string | null;
    setCurrentWallpaperUrl: (url: string | null) => void;
    getCurrentWallpaperMetadata: () => WallpaperMetadata | null;
    setCurrentWallpaperMetadata: (metadata: WallpaperMetadata | null) => void;
    getCurrentSolidBackground: () => string | null;
    setCurrentSolidBackground: (value: string | null) => void;
    applyWallpaperOverlay: (value: string) => void;
    scheduleWallpaperRefresh: () => void;
}

type AddThemeManagerCleanup = (cleanup: () => void) => void;

type RunDetachedWithBoundary = (operationName: string, task: () => Promise<void>) => void;

type CustomizationType = 'sidebar' | 'dashboard';

interface ThemeViewContext {
    host: ThemeManagerHost;
    canManageSolidBackground: boolean;
    canManageWallpaper: boolean;
    grantedActions: ReadonlySet<string>;
    getPreferenceStateLabels: () => ToggleLabelState;
}

export type { AddThemeManagerCleanup, CustomizationType, RunDetachedWithBoundary, ThemeManagerDependencies, ThemeManagerHost, ThemeViewContext };
