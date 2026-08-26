/* SoAI - Models page card renderer contracts [frontend/assets/ts/pages/models/rendering/cardrenderer/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ModelData, ModelRecord } from '@core/types/modelTypes.ts';
import type { BaseCardRendererOptions, CardRendererHost } from '@core/ui/BaseCardRenderer.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

interface CardData {
    cardId: string | number | null;
    status: string | null;
    statusClass: string;
    statusBadgeClass: string;
    statusLabel: string | null;
    pluginName: string | null;
    providerName: string | null;
    baseIdentifier: string | null;
}

interface MetricsBuildResult {
    metricsMarkup: string;
    statusBadgeClass: string;
    statusLabel: string;
    providerLabel: string;
}

interface ModelCardPresentationPort {
    sanitizeText(value: string | null | undefined, options?: Record<string, string | null>): string;
    getIconSync(iconName: IconName, options?: IconOptions): TrustedHtml;
    getModelIcon(item: ModelData, pluginName: string): TrustedHtml;
}

interface ModelCardIdentityPort {
    getItemCardId(item: ModelData): string | number;
    getModelPlugin(item: ModelData): string | null;
    getModelProvider(item: ModelData): string | null;
    getModelOriginId(item: ModelData): string | null;
    extractCleanModelId(identifier: string): string;
    getModelDisplayName(item: ModelData): string | null;
}

interface ModelCardStatusPort {
    getModelStatus(item: ModelRecord): string | null;
    presenter: {
        getDescription(status: string): string;
        getCollectionStatusClass(status: string): string;
        getCollectionBadgeClass(status: string): string;
        normalizeStatus(status: JsonValue | null | undefined): string;
    };
    getPendingToggleTarget(item: ModelRecord): boolean | null;
    canDeleteModel(item: ModelRecord): boolean;
    isExternalProviderModel(item: ModelRecord): boolean;
    isModelFromPersistentPlugin(item: ModelRecord): boolean;
    isNewItem(item: ModelRecord): boolean;
}

interface ModelCardMetricsPort {
    formatStrategyLabel(strategy: JsonValue | null | undefined): string;
    formatNumber(number: number, options?: JsonObject): string;
    resolveModelRequestCount(item: ModelData): number;
    resolveModelTokenCount(item: ModelData): number;
}

interface ModelCardHost extends CardRendererHost {
    sanitizeClassName(value: string | null | undefined, fallback: string, options?: Record<string, string | null>): string;
    presentation: ModelCardPresentationPort;
    identity: ModelCardIdentityPort;
    status: ModelCardStatusPort;
    metrics: ModelCardMetricsPort;
}

interface ModelCardRendererOptions extends BaseCardRendererOptions {
    host: ModelCardHost;
    activeStatuses?: readonly string[];
}

export type { CardData, MetricsBuildResult, ModelCardHost, ModelCardRendererOptions };
