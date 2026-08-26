/* SoAI - Shared layout sidebar actions [frontend/assets/ts/core/layout/sidebar/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type SidebarReadyEventName = 'soai:sidebar:ready';
type SidebarDestroyedEventName = 'soai:sidebar:destroyed';
type SidebarCustomizationChangedEventName = 'soai:sidebar:customization:changed';
type SidebarLanguageChangedEventName = 'soai:language:changed';

const SIDEBAR_READY_EVENT: SidebarReadyEventName = 'soai:sidebar:ready';
const SIDEBAR_DESTROYED_EVENT: SidebarDestroyedEventName = 'soai:sidebar:destroyed';
const SIDEBAR_CUSTOMIZATION_CHANGED_EVENT: SidebarCustomizationChangedEventName = 'soai:sidebar:customization:changed';
const SIDEBAR_LANGUAGE_CHANGED_EVENT: SidebarLanguageChangedEventName = 'soai:language:changed';

const FEATURES_SERVICE_PREFIX = 'features.';

export { FEATURES_SERVICE_PREFIX, SIDEBAR_READY_EVENT, SIDEBAR_DESTROYED_EVENT, SIDEBAR_CUSTOMIZATION_CHANGED_EVENT, SIDEBAR_LANGUAGE_CHANGED_EVENT };

export type { SidebarReadyEventName, SidebarDestroyedEventName, SidebarCustomizationChangedEventName, SidebarLanguageChangedEventName };
