/* SoAI - Shared UI primitives viewmode contracts [frontend/assets/ts/core/uiprimitives/viewmode/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

type ViewMode = 'cards' | 'list' | 'icons';

interface ViewModeOption {
    mode: ViewMode;
    icon: IconName;
    label: string;
    pressed: boolean;
}

interface ViewModeControllerOptions {
    root: HTMLElement;
    button: HTMLButtonElement;
    modes: readonly [ViewMode, ViewMode];
    activeMode: ViewMode;
    storageKey: string;
    labels: Record<ViewMode, string>;
    icons: Record<ViewMode, IconName>;
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
    onModeChanging?: ((mode: ViewMode) => void) | undefined;
    onModeChanged?: ((mode: ViewMode) => void) | undefined;
}

type ViewModeValidator = (value: JsonValue | null | undefined) => value is ViewMode;

export type { ViewMode, ViewModeControllerOptions, ViewModeOption, ViewModeValidator };
