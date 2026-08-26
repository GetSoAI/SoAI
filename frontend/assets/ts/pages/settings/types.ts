/* SoAI - Settings page public contracts [frontend/assets/ts/pages/settings/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GenerateStandardHeaderOptions, HeaderActionDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

export interface SettingsUi {
    root: HTMLElement;
    pageActionRoot: HTMLElement;
    tabsContainer: HTMLElement;
    content: HTMLElement;
    searchContainer: HTMLElement;
    saveButton: HTMLButtonElement;
    advancedModeToggleButton: HTMLButtonElement | null;
}

export type SettingsViewDependencies = {
    generateStandardHeader: (options: GenerateStandardHeaderOptions) => TrustedHtml;
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
    canAccessAdvanced: boolean;
    advancedMode: boolean;
};

export type SettingsHeaderAction = HeaderActionDefinition;
