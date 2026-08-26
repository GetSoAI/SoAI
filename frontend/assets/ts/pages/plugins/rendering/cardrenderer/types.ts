/* SoAI - Plugins page card renderer contracts [frontend/assets/ts/pages/plugins/rendering/cardrenderer/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CompatibilityInfo } from '@core/types/catalogPluginTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { CardRendererHost } from '@core/ui/BaseCardRenderer.ts';

interface PluginStatusPresenter {
    getCollectionStatusClass(status: string): string;
    getDescription(status: string): string;
    getCollectionBadgeClass(status: string): string;
}

interface PluginCardHost extends CardRendererHost {
    status: {
        presenter: PluginStatusPresenter;
        getPluginStatus(plugin: PluginRecord): string;
        getBackendStatus(plugin: PluginRecord): string;
        getBackendAvailableVariantCount(plugin: PluginRecord): number | null;
    };
    compatibility: {
        isHardwareIncompatible(plugin: PluginRecord): boolean;
        isCircuitBreakerActive(plugin: PluginRecord): boolean;
        getCircuitBreakerInfo(plugin: PluginRecord): JsonValue;
        requiresCompatibilityOverride(plugin: PluginRecord): boolean;
        isPluginPermanentlyDisabled(plugin: PluginRecord): boolean;
        getPluginCompatibility(plugin: PluginRecord): CompatibilityInfo;
    };
    presentation: {
        getPluginLogo(plugin: PluginRecord): string;
        formatPluginName(name: string | undefined): string;
        getCircuitBreakerNotice(plugin: PluginRecord): string;
        getIncompatibleNotice(plugin: PluginRecord): string;
        sanitizeText(value: JsonValue, options?: Record<string, JsonValue>): string;
    };
    actions: {
        getPendingToggleTarget(plugin: PluginRecord): boolean | null;
        getItemCardId(plugin: PluginRecord): string | null;
        isNewItem(plugin: PluginRecord): boolean;
        supportsPluginCloning?(plugin: PluginRecord): boolean;
        isPluginStoppable(plugin: PluginRecord): boolean;
    };
}

interface PluginCardRendererConstants {
    classNames: {
        disabled: string;
    };
    statuses: {
        backendNotInstalled: string;
        backendInstalling: string;
        incompatible: string;
        quarantined: string;
    };
}

interface PluginCardRendererOptions {
    host: PluginCardHost;
    constants: PluginCardRendererConstants;
}

interface PluginCardData {
    cardId: string | null;
    hardwareIncompatible: boolean;
    status: string;
    statusClass: string;
    statusLabel: string;
    statusBadgeClass: string;
    circuitBreakerActive: boolean;
    overrideRequired: boolean;
}

interface ActionState {
    hasConfigAction: boolean;
    hasCloneAction: boolean;
}

interface ActionContext {
    plugin: PluginRecord;
    actionState: ActionState;
}

interface RenderCardContentDependencies {
    plugin: PluginRecord;
    data: PluginCardData;
    host: PluginCardHost;
    constants: PluginCardRendererConstants;
}

export type { PluginRecord, PluginCardHost, PluginCardRendererConstants, PluginCardRendererOptions, PluginCardData, ActionState, ActionContext, RenderCardContentDependencies };
