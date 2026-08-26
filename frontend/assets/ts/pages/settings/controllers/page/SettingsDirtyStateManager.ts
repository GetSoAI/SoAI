/* SoAI - Settings page dirty state manager [frontend/assets/ts/pages/settings/controllers/page/SettingsDirtyStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { ConfigurationManager } from '@core/configurationManager.ts';
import { createSettingsConfigFieldKey, createSettingsManualFieldKey, parseSettingsFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import type { SettingsDirtyStateSurface, SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';

interface SettingsDirtyStateDependencies {
    pageDom: PageDom;
    getData(element: Element, key: string): string | null;
}

class SettingsDirtyStateManager implements SettingsDirtyStateSurface {
    readonly #dependencies: SettingsDirtyStateDependencies;
    readonly #state: SettingsPageState;
    readonly #configSurfaceIndex = new Map<string, Element[]>();
    readonly #fieldKeySurfaceIndex = new Map<string, Element[]>();
    readonly #indexedSurfaces: Element[] = [];
    #tracker: FieldStateTracker;
    #surfaceIndexReady = false;

    constructor(dependencies: SettingsDirtyStateDependencies, state: SettingsPageState) {
        this.#dependencies = dependencies;
        this.#state = state;
        this.#tracker = this.#createTracker();
    }

    initialize(): void {
        this.#clearSurfaceIndex();
        this.#tracker = this.#createTracker();
    }

    syncConfigField(path: string, valid: boolean): void {
        const fieldKey = createSettingsConfigFieldKey(path);
        this.#tracker.setInvalid(fieldKey, valid ? null : 'invalid');
        this.#tracker.update(fieldKey);
    }

    syncUiPreferenceField(sourceKey: string): void {
        for (const fieldKey of this.#collectRenderedFieldKeys()) {
            const parsed = parseSettingsFieldKey(fieldKey);
            if (parsed?.fieldType === 'ui' && parsed.sourceKey === sourceKey) {
                this.#tracker.update(fieldKey);
            }
        }
    }

    syncManualField(key: string, modified: boolean, valid: boolean): void {
        const fieldKey = createSettingsManualFieldKey(key);
        this.#tracker.setInvalid(fieldKey, valid ? null : 'invalid');
        this.#tracker.setModified(fieldKey, modified);
    }

    clearManualField(key: string): void {
        this.#tracker.clear(createSettingsManualFieldKey(key));
    }

    refreshRenderedFields(): void {
        for (const path of this.#collectRenderedConfigPaths()) {
            this.#tracker.update(createSettingsConfigFieldKey(path));
        }
        for (const fieldKey of this.#collectRenderedFieldKeys()) {
            const parsed = parseSettingsFieldKey(fieldKey);
            if (parsed?.fieldType === 'ui') {
                this.#tracker.update(fieldKey);
            }
        }
        this.#tracker.reapplyDomState();
    }

    clearAll(): void {
        this.#tracker.clearAll();
        this.#clearSurfaceIndex();
    }

    hasInvalidFields(): boolean {
        return !this.#tracker.isValid();
    }

    #createTracker(): FieldStateTracker {
        return new FieldStateTracker({
            getElement: (key: string): Element | null => this.#resolveElements(key)[0] ?? null,
            getElements: (key: string): Element[] => this.#resolveElements(key),
            getCurrentValue: (key: string): JsonValue | undefined => this.#resolveCurrentValue(key),
            getOriginalValue: (key: string): JsonValue | undefined => this.#resolveOriginalValue(key),
            comparator: (current: JsonValue | null | undefined, original: JsonValue | null | undefined, key: string): boolean => {
                if (!isJsonValue(current) || !isJsonValue(original)) {
                    return current === original;
                }
                return this.#areValuesEqual(key, current, original);
            }
        });
    }

    #resolveElements(fieldKey: string): Element[] {
        const parsed = parseSettingsFieldKey(fieldKey);
        if (!parsed) {
            return [];
        }
        if (parsed.fieldType === 'config') {
            return this.#findConfigSurfaces(parsed.sourceKey);
        }
        return this.#findFieldKeySurfaces(fieldKey);
    }

    #findConfigSurfaces(path: string): Element[] {
        this.#ensureSurfaceIndex();
        return this.#configSurfaceIndex.get(path) ?? [];
    }

    #findFieldKeySurfaces(fieldKey: string): Element[] {
        this.#ensureSurfaceIndex();
        return this.#fieldKeySurfaceIndex.get(fieldKey) ?? [];
    }

    #collectRenderedConfigPaths(): string[] {
        this.#rebuildSurfaceIndex();
        return Array.from(this.#configSurfaceIndex.keys());
    }

    #collectRenderedFieldKeys(): string[] {
        this.#ensureSurfaceIndex();
        return Array.from(this.#fieldKeySurfaceIndex.keys());
    }

    #ensureSurfaceIndex(): void {
        if (!this.#surfaceIndexReady || this.#indexedSurfaces.some((surface) => !surface.isConnected)) {
            this.#rebuildSurfaceIndex();
        }
    }

    #rebuildSurfaceIndex(): void {
        this.#clearSurfaceIndex();
        for (const surface of this.#dependencies.pageDom.query('.setting-change-surface')) {
            this.#indexedSurfaces.push(surface);
            const surfacePath = this.#dependencies.getData(surface, 'path');
            if (surfacePath) {
                this.#appendIndexedSurface(this.#configSurfaceIndex, surfacePath, surface);
            }
            const fieldKey = this.#dependencies.getData(surface, 'fieldKey');
            if (fieldKey) {
                this.#appendIndexedSurface(this.#fieldKeySurfaceIndex, fieldKey, surface);
            }
            for (const element of this.#dependencies.pageDom.query('[data-path]', surface)) {
                const path = this.#dependencies.getData(element, 'path');
                if (path) {
                    this.#appendIndexedSurface(this.#configSurfaceIndex, path, surface);
                }
            }
        }
        this.#surfaceIndexReady = true;
    }

    #clearSurfaceIndex(): void {
        this.#configSurfaceIndex.clear();
        this.#fieldKeySurfaceIndex.clear();
        this.#indexedSurfaces.length = 0;
        this.#surfaceIndexReady = false;
    }

    #appendIndexedSurface(index: Map<string, Element[]>, key: string, surface: Element): void {
        const existing = index.get(key);
        if (existing) {
            if (!existing.includes(surface)) {
                existing.push(surface);
            }
            return;
        }
        index.set(key, [surface]);
    }

    #resolveCurrentValue(fieldKey: string): JsonValue | undefined {
        const parsed = parseSettingsFieldKey(fieldKey);
        if (parsed?.fieldType === 'config') {
            return this.#requireConfigManager().getValue(parsed.sourceKey);
        }
        if (parsed?.fieldType === 'ui') {
            return this.#requireUiPrefsManager().getValue(parsed.sourceKey);
        }
        return undefined;
    }

    #resolveOriginalValue(fieldKey: string): JsonValue | undefined {
        const parsed = parseSettingsFieldKey(fieldKey);
        if (parsed?.fieldType === 'config') {
            const manager = this.#requireConfigManager();
            return manager.getValueByPath(manager.originalData, parsed.sourceKey);
        }
        if (parsed?.fieldType === 'ui') {
            const manager = this.#requireUiPrefsManager();
            return manager.getValueByPath(manager.originalData, parsed.sourceKey);
        }
        return undefined;
    }

    #areValuesEqual(fieldKey: string, current: JsonValue | undefined, original: JsonValue | undefined): boolean {
        const parsed = parseSettingsFieldKey(fieldKey);
        const manager = parsed?.fieldType === 'ui' ? this.#state.uiPrefsManager : this.#state.configManager;
        if (!manager) {
            return current === original;
        }
        return manager.areValuesEqual(current, original);
    }

    #requireConfigManager(): ConfigurationManager {
        const manager = this.#state.configManager;
        if (!manager) {
            throw new Error('Settings config manager is not initialized');
        }
        return manager;
    }

    #requireUiPrefsManager(): ConfigurationManager {
        const manager = this.#state.uiPrefsManager;
        if (!manager) {
            throw new Error('Settings UI preferences manager is not initialized');
        }
        return manager;
    }
}

export { SettingsDirtyStateManager };
export type { SettingsDirtyStateDependencies };
