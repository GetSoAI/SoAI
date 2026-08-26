/* SoAI - Shared background tasks contracts [frontend/assets/ts/core/backgroundtasks/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RouteDefinition } from '@core/routing/router/types.ts';

type BackgroundRouteDescriptor = RouteDefinition & {
    name?: string;
    pageId?: string;
    id?: string;
};

type BackgroundRoute = BackgroundRouteDescriptor | string | null;

interface StorageInstance {
    getSolidBackground: () => string | null;
    getWallpaperOverlay: () => number;
}

interface AuthInstance {
    isAuthenticated: boolean;
}

export type { AuthInstance, BackgroundRoute, BackgroundRouteDescriptor, StorageInstance };
