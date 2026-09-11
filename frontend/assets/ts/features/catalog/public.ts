/* SoAI - Catalog feature public surface [frontend/assets/ts/features/catalog/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { getCapabilityDescriptors, getOpenAIDescriptors, resolveOpenAIModalityDescriptor, resolveOpenAITokenDescriptor } from '@features/catalog/capabilityPresenter.ts';
export type { CapabilityDescriptor, OpenAICategory } from '@features/catalog/capabilityPresenter.ts';
export { setupCatalogBackedCollection } from '@features/catalog/catalogCollectionPage.ts';
export { createCatalogSubscriptionManager } from '@features/catalog/catalogSubscriptionManager.ts';
export type { CatalogStore, CatalogSubscriptionManager } from '@features/catalog/catalogSubscriptionManager.ts';
export { getPluginArchiveLogoPath, getPluginFallbackLogoPath, getPluginLogoPath, getPluginLogoPresentation } from '@features/catalog/pluginAssets.ts';
export type { PluginLogoPresentation } from '@features/catalog/pluginAssets.ts';
export { bindPluginLogoFallbacks, setPluginLogoFallback } from '@features/catalog/pluginLogoFallback.ts';
export { stablePluginFingerprint } from '@features/catalog/pluginFingerprint.ts';
export { isHardwareCompatibilityAcknowledged, PROVIDER_MODE, resolveProviderMode } from '@features/catalog/pluginNormalization.ts';
export type { CircuitBreakerInfo, CompatibilityInfo } from '@features/catalog/pluginNormalization.ts';
export { requireCatalogStore } from '@features/catalog/service.ts';
