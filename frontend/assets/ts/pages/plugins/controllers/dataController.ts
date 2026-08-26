/* SoAI - Plugins page data controller [frontend/assets/ts/pages/plugins/controllers/dataController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { formatTitleFromId } from '@core/primitives/text.ts';
import { normalizeVersion } from '@core/primitives/version.ts';
import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import { PLUGIN_ACTIVE_STATUSES, PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_DELETE_ERROR, PLUGIN_STATUS_DISABLED, PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_PERSISTENT_READY, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_UNKNOWN, PLUGIN_STATUS_UPDATE_ERROR } from '@core/state/pluginStatus.ts';
import { isArray, isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import { isNamedPluginRecord } from '@core/types/pluginRecordGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { getCapabilityDescriptors, getPluginLogoPath, PROVIDER_MODE, resolveProviderMode, type CatalogStore, type CircuitBreakerInfo, type CompatibilityInfo } from '@features/catalog/public.ts';
import { PLUGIN_FILTER_ACTIVE } from '@features/plugins/public.ts';

interface PluginsDataControllerDependencies {
    catalogStore: CatalogStore;
    setItemsFromList(items: ResourceItem[]): void;
    reapplyCollection(): void;
    notifyPluginIncompatible(plugin: PluginRecord): void;
    notifyOverrideRequired(plugin: PluginRecord): void;
}

class PluginsDataController {
    readonly #dependencies: PluginsDataControllerDependencies;

    constructor(dependencies: PluginsDataControllerDependencies) {
        this.#dependencies = dependencies;
    }

    resolvePluginRecord(plugin: PluginRecord | ResourceIncomingValue | string | null | undefined): PluginRecord | null {
        if (!plugin) return null;
        const name = isString(plugin) ? toTrimmedString(plugin) : isObject(plugin) && !isArray(plugin) ? toTrimmedString(plugin['name']) : '';
        if (!name) return null;
        const store = this.#dependencies.catalogStore;
        const stored = store.getPlugin(name);
        if (isNamedPluginRecord(stored)) return stored;
        return null;
    }

    applyCatalogSnapshot(plugins: JsonValue, reapply: boolean): void {
        if (isArray(plugins)) {
            const items: ResourceItem[] = [];
            for (const plugin of plugins) {
                if (isObject(plugin)) items.push(plugin);
            }
            this.#dependencies.setItemsFromList(items);
        }
        if (reapply) this.#dependencies.reapplyCollection();
    }

    getPluginCompatibility(plugin: PluginRecord | string | null | undefined): CompatibilityInfo {
        const store = this.#dependencies.catalogStore;
        const record = this.resolvePluginRecord(plugin);
        return store.getPluginCompatibility(record);
    }

    getCircuitBreakerInfo(plugin: PluginRecord | string | null | undefined): CircuitBreakerInfo | null {
        const store = this.#dependencies.catalogStore;
        const record = this.resolvePluginRecord(plugin);
        return store.getCircuitBreakerInfo(record);
    }

    isCircuitBreakerActive(plugin: PluginRecord | string | null | undefined): boolean {
        const store = this.#dependencies.catalogStore;
        const record = this.resolvePluginRecord(plugin);
        return record ? store.isCircuitBreakerActive(record) : false;
    }

    isPluginPermanentlyDisabled(plugin: PluginRecord | string | null | undefined): boolean {
        const store = this.#dependencies.catalogStore;
        const record = this.resolvePluginRecord(plugin);
        return record ? store.isPluginPermanentlyDisabled(record) : false;
    }

    supportsPluginCloning(plugin: PluginRecord | string | null | undefined): boolean {
        const record = this.resolvePluginRecord(plugin);
        return record ? !this.isPluginIncompatible(record) && record.capabilities?.supportsCloning === true : false;
    }

    isPluginIncompatible(plugin: PluginRecord | string | null | undefined): boolean {
        const comp = this.resolvePluginRecord(plugin)?.compatibility;
        return Boolean(comp?.reason && comp.isOverridden !== true);
    }

    isHardwareIncompatible(plugin: PluginRecord | string | null | undefined): boolean {
        const compatibility = this.getPluginCompatibility(plugin);
        return Boolean(compatibility?.reason && compatibility.canOverride === true && compatibility.isOverridden !== true);
    }

    requiresCompatibilityOverride(plugin: PluginRecord | string | null | undefined): boolean {
        const compatibility = this.resolvePluginRecord(plugin)?.compatibility;
        return Boolean(compatibility?.reason && compatibility?.canOverride && compatibility?.isOverridden !== true);
    }

    canExecutePluginAction(plugin: PluginRecord | string | null | undefined, { notify = true, allowCompatibilityOverride = false }: { notify?: boolean; allowCompatibilityOverride?: boolean } = {}): boolean {
        const record = this.resolvePluginRecord(plugin);
        if (!record) return false;
        if (this.isPluginPermanentlyDisabled(record)) {
            if (notify) this.#dependencies.notifyPluginIncompatible(record);
            return false;
        }
        if (this.requiresCompatibilityOverride(record) && !(allowCompatibilityOverride && this.isHardwareIncompatible(record))) {
            if (notify) this.#dependencies.notifyOverrideRequired(record);
            return false;
        }
        return true;
    }

    resolveMaxConcurrentPlugins(config: JsonObject | null): number | null {
        const configObject = isJsonObject(config) ? config : null;
        const modelsCandidate = configObject ? configObject['MODELS'] : null;
        const models = isJsonObject(modelsCandidate) ? modelsCandidate : null;
        const routingCandidate = models ? models['ROUTING'] : null;
        const routing = isJsonObject(routingCandidate) ? routingCandidate : null;
        const rawRoutingMax = routing ? routing['MAX_CONCURRENT_PLUGINS'] : null;
        const source = rawRoutingMax;
        const value = Number.parseInt(String(source ?? ''), 10);
        return Number.isFinite(value) && value > 0 ? value : null;
    }

    normalizeVersion(value: JsonValue | null | undefined): { raw: string | null; safe: string | null } {
        const normalized = normalizeVersion(value ?? null);
        if (normalized.raw === null) errorHandler?.warn?.('PluginsPage', 'Version value is missing');
        else if (!normalized.safe) errorHandler?.warn?.('PluginsPage', 'Version value is empty');
        return normalized;
    }

    formatPluginName(name: string): string {
        return formatTitleFromId(name);
    }

    getBackendStatus(plugin: PluginRecord | string | null | undefined): string {
        const record = this.resolvePluginRecord(plugin);
        if (!record) return i18n.t('plugins.status.installed');
        if (this.isPluginPermanentlyDisabled(record)) return i18n.t('plugins.status.incompatible');
        if (record.capabilities?.supportsBackendInstallation === false) return i18n.t('plugins.status.notSupported');
        const state = String(record.state ?? '').toUpperCase();
        if (state === PLUGIN_STATUS_BACKEND_INSTALLING) {
            return i18n.t('plugins.status.installing');
        }
        if (state === PLUGIN_STATUS_BACKEND_UPDATING) {
            return i18n.t('plugins.status.updating');
        }
        if (state === PLUGIN_STATUS_INSTALL_ERROR) {
            return i18n.t('plugins.status.installError');
        }
        if (state === PLUGIN_STATUS_LOAD_ERROR) {
            return i18n.t('plugins.status.loadError');
        }
        if (state === PLUGIN_STATUS_UPDATE_ERROR) {
            return i18n.t('plugins.status.updateError');
        }
        if (state === PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR) {
            return i18n.t('plugins.status.backendUninstallError');
        }
        if (state === PLUGIN_STATUS_DELETE_ERROR) {
            return i18n.t('plugins.status.deleteError');
        }
        if (state === PLUGIN_STATUS_BACKEND_NOT_INSTALLED) {
            return i18n.t('plugins.status.notInstalled');
        }
        return i18n.t('plugins.status.installed');
    }

    getProviderCount(plugin: PluginRecord | string | null | undefined): number {
        return this.resolvePluginRecord(plugin)?.stats?.providerCount ?? 0;
    }

    getBackendAvailableVariantCount(plugin: PluginRecord | string | null | undefined): number | null {
        const value = this.resolvePluginRecord(plugin)?.stats?.backendVariantAvailableCount;
        return isFiniteNumber(value) && value >= 0 ? value : null;
    }

    getPluginStatus(plugin: PluginRecord | string | null | undefined): string {
        const record = this.resolvePluginRecord(plugin);
        if (!record) return PLUGIN_STATUS_UNKNOWN;
        const raw = record.state || (record.isEnabled ? 'IDLE' : PLUGIN_STATUS_DISABLED);
        return String(raw).trim().toUpperCase() || PLUGIN_STATUS_DISABLED;
    }

    isPluginStoppable(plugin: PluginRecord | string | null | undefined): boolean {
        const record = this.resolvePluginRecord(plugin);
        if (!record || this.isPluginPermanentlyDisabled(record)) return false;
        if (record.isPersistent === true) return false;
        const status = this.getPluginStatus(record);
        return status !== PLUGIN_STATUS_PERSISTENT_READY && status !== PLUGIN_STATUS_BACKEND_INSTALLING && PLUGIN_ACTIVE_STATUSES.has(status);
    }

    getPluginLogo(plugin: PluginRecord | null | undefined): string {
        return getPluginLogoPath(plugin);
    }

    getItemCardId(item: PluginRecord | ResourceIncomingValue | null | undefined): string | null {
        if (!item || !isObject(item) || isArray(item)) return null;
        const name = toTrimmedString(item['name']);
        if (name) return name;
        const id = toTrimmedString(item['id']);
        return id || null;
    }

    getItemSearchFields(plugin: PluginRecord | ResourceIncomingValue): string[] {
        const record = this.resolvePluginRecord(plugin);
        if (!record) return [];
        const fields: string[] = [];
        const base = [toTrimmedString(record.name), toTrimmedString(record.displayName), toTrimmedString(record.descriptionSoaiplugin), toTrimmedString(record.authorSoaiplugin), toTrimmedString(record.versionSoaiplugin)];
        for (const entry of base) {
            if (entry) fields.push(entry);
        }
        const descriptors = getCapabilityDescriptors(record);
        for (const descriptor of descriptors) {
            const label = toTrimmedString(descriptor?.label);
            if (label) fields.push(label);
        }
        const mode = resolveProviderMode(record);
        if (mode === PROVIDER_MODE.PLUGIN_MANAGED) {
            fields.push(i18n.t('plugins.providerMode.labels.pluginManaged'));
        } else if (mode === PROVIDER_MODE.USER_MANAGED) {
            fields.push(i18n.t('plugins.providerMode.labels.userManaged'));
        }
        return fields;
    }

    applyCustomFilters(plugin: PluginRecord | ResourceIncomingValue, { filterProvider, filterStatus }: { filterProvider: string; filterStatus: string }): boolean {
        const record = this.resolvePluginRecord(plugin);
        if (!record) return false;
        const status = this.getPluginStatus(record);
        if (filterProvider === PLUGIN_FILTER_ACTIVE && !PLUGIN_ACTIVE_STATUSES.has(status)) return false;
        if (filterProvider === 'inactive' && PLUGIN_ACTIVE_STATUSES.has(status)) return false;
        if (filterStatus === 'all') return true;
        if (filterStatus === 'builtin') return Boolean(record.isBuiltin);
        return filterStatus !== 'thirdparty' || !record.isBuiltin;
    }

    isValidItem(candidate: ResourceIncomingValue | PluginRecord | null | undefined): boolean {
        return isNamedPluginRecord(candidate);
    }
}

export { PluginsDataController };
