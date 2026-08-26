/* SoAI - Shared UI tabs contracts [frontend/assets/ts/core/ui/controls/tabs/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';

interface TabConfig {
    id: string;
    label: string;
    icon?: TrustedHtml | string | undefined;
    badge?: string | number | undefined;
    notifyBadge?: string | number | undefined;
}

interface RightButtonConfig {
    id: string;
    label: string;
    icon?: TrustedHtml | string | undefined;
    className?: string | undefined;
    disabled?: boolean | undefined;
    persistent?: boolean | undefined;
    action?: (() => void) | undefined;
}

interface TabsOptions {
    tabs?: TabConfig[] | undefined;
    rightButtons?: Record<string, RightButtonConfig[]> | undefined;
    activeTab?: string | null | undefined;
    onTabChange?: ((activeTab: string, previousTab: string | null) => void) | null | undefined;
    className?: string | undefined;
    enableOverflowNav?: boolean | undefined;
    navScrollAmount?: number | undefined;
}

export type { RightButtonConfig, TabConfig, TabsOptions };
