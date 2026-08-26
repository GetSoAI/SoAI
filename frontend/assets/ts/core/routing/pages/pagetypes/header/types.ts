/* SoAI - Shared routing header contracts [frontend/assets/ts/core/routing/pages/pagetypes/header/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

export type HeaderStatActionTone = 'neutral' | 'primary' | 'violet';

export interface HeaderStatInlineEditDefinition {
    startActionId: string;
    saveActionId: string;
    cancelActionId: string;
    inputId: string;
    editLabel: string;
    saveLabel: string;
    cancelLabel: string;
}

export interface HeaderStatActionDefinition {
    actionId: string;
    label: string;
    buttonId?: string;
    icon?: TrustedHtml | string;
    iconName?: IconName;
    tone?: HeaderStatActionTone;
    disabled?: boolean;
}

export interface HeaderStatDefinition {
    id: string;
    label: string;
    actions?: readonly HeaderStatActionDefinition[];
    inlineEdit?: HeaderStatInlineEditDefinition;
}

export type HeaderActionVariant = 'ui-variant-neutral' | 'ui-variant-accent' | 'ui-variant-danger' | 'ui-variant-warning' | 'ui-variant-primary' | 'ui-variant-violet';

interface HeaderActionDefinitionBase {
    id?: string;
    variant?: HeaderActionVariant;
    class?: string;
    attributes?: Record<string, JsonValue | null | undefined>;
    content?: TrustedHtml | string;
    html?: TrustedHtml | string;
    filter?: FilterDefinition;
}

interface HeaderButtonActionDefinition extends HeaderActionDefinitionBase {
    type: 'button';
    ariaLabel: string;
}

interface HeaderPassiveActionDefinition extends HeaderActionDefinitionBase {
    type: 'search' | 'filter' | 'custom';
    ariaLabel?: string;
}

export type HeaderActionDefinition = HeaderButtonActionDefinition | HeaderPassiveActionDefinition;

export interface FilterDefinition {
    type: 'select' | 'input';
    id?: string;
    icon?: TrustedHtml;
    selectionPrefix?: string;
    attributes?: Record<string, JsonValue | null | undefined>;
    options?: Array<{ value: string; label: string; selected?: boolean; standaloneSelectionLabel?: boolean }>;
    placeholder?: string;
    html?: TrustedHtml | string;
}

export interface TabsDefinition {
    containerId?: string;
    html?: TrustedHtml | string;
}

export interface HeaderToolbarsDefinition {
    id?: string;
    ariaLabel?: string;
    html: TrustedHtml;
}

export interface GenerateStandardHeaderOptions {
    containerClass?: string;
    floating?: boolean;
    detachedHeaderMode?: 'hide' | 'show';
    title?: string;
    description?: string;
    icon?: IconName | null;
    actions?: HeaderActionDefinition[];
    stats?: HeaderStatDefinition[];
    toolbars?: HeaderToolbarsDefinition | null;
    tabs?: TabsDefinition | null;
    contentAreaClass?: string;
    contentLayout?: 'collections' | 'card-grid' | 'sections' | 'analytics' | null;
    role?: string;
    ariaLabel?: string | null;
    responsive?: Record<
        string,
        {
            stackActions?: boolean;
            hideElements?: string[];
        }
    >;
}

export interface CreateStandardSearchOptions {
    placeholder: string;
    onSearch?: (value: string) => void;
    onClear?: () => void;
    debounceTime?: number;
    showIconOnMobile?: boolean;
}

export interface StandardSearchResult {
    input: HTMLInputElement;
    setValue: (value: string) => void;
}

export type IconDefinition = IconName | [IconName, IconOptions?] | { icon?: IconName; name?: IconName; options?: IconOptions };

export interface HeaderStatsLayout {
    container: HTMLElement;
}
