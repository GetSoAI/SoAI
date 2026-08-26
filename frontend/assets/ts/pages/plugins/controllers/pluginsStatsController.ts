/* SoAI - Plugins page stats controller [frontend/assets/ts/pages/plugins/controllers/pluginsStatsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { resolveHeaderStatCard, resolveHeaderStatLabel } from '@core/routing/pages/basepagelayout/headerStats.ts';
import { isArray } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { LatestUsageResource } from '@core/realtime/streammanager/resources/latestUsageResource.ts';
import { PLUGINS_ACTION_STOP_ALL } from '@features/plugins/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface PluginsStatsControllerHost extends PageDomOwnerHost {
    getCollectionPlugins(): PluginRecord[] | null;
    getPluginStatus(plugin: PluginRecord): string;
    isPluginStoppable(plugin: PluginRecord): boolean;
    getMaxConcurrentPlugins(): number | null;
    findPlugin(pluginName: string): PluginRecord | null;
    formatPluginName(name: string): string;
    updateHeaderStat(id: string, key: string, value: number | string): void;
    queueResponsiveLayoutUpdate(): void;
}

interface PluginsStatsControllerOptions {
    host: PluginsStatsControllerHost;
    classes: {
        hidden: string;
    };
    statuses: {
        activeStatusSet: ReadonlySet<string>;
    };
}

class PluginsStatsController {
    #host: PluginsStatsControllerHost;
    #classes: {
        hidden: string;
    };
    #statuses: {
        activeStatusSet: ReadonlySet<string>;
    };
    #currentLatestUsage: LatestUsageResource | null = null;
    #lastUsedSignature: string | null = null;

    constructor(options: PluginsStatsControllerOptions) {
        this.#host = options.host;
        this.#classes = options.classes;
        this.#statuses = options.statuses;
    }

    updateStats(): void {
        const plugins = this.#host.getCollectionPlugins();
        if (!plugins) {
            return;
        }
        let active = 0;
        let persistent = 0;
        for (const plugin of plugins) {
            const status = this.#host.getPluginStatus(plugin);
            if (this.#statuses.activeStatusSet.has(status)) {
                active += 1;
            }
            if (plugin.isPersistent) {
                persistent += 1;
            }
        }
        const stats = {
            total: plugins.length,
            active,
            persistent,
            concurrent: this.#host.getMaxConcurrentPlugins()
        };
        this.#host.updateHeaderStat('total-plugins', i18n.plural('plugins.stats.totalPlugins', stats.total, {}), stats.total);
        this.#host.updateHeaderStat('active-plugins', i18n.plural('plugins.stats.activePlugins', stats.active, {}), stats.active);
        this.#host.updateHeaderStat('persistent-plugins', i18n.plural('plugins.stats.persistentPlugins', stats.persistent, {}), stats.persistent);

        const concurrentElement = this.#host.pageDom.optional('max-concurrent-plugins');
        if (concurrentElement) {
            if (Number.isFinite(stats.concurrent) && stats.concurrent !== null) {
                this.#host.updateHeaderStat('max-concurrent-plugins', i18n.plural('plugins.stats.concurrentPlugins', stats.concurrent, {}), stats.concurrent);
            } else {
                this.#host.pageDom.updateText(concurrentElement, i18n.t('common.notAvailableShort'));
                const label = resolveHeaderStatLabel(resolveHeaderStatCard(concurrentElement));
                if (label) {
                    this.#host.pageDom.updateText(label, i18n.t('plugins.stats.concurrentPlugins.plural'));
                }
            }
        }

        this.updateStopAllButtonVisibility();
        this.#applyLastUsedStat();
        this.#host.queueResponsiveLayoutUpdate();
    }

    #applyLastUsedStat(latestUsage?: LatestUsageResource): boolean {
        if (latestUsage !== undefined) this.#currentLatestUsage = latestUsage;
        const identity = this.#currentLatestUsage?.identity ?? null;
        const plugin = identity ? this.#host.findPlugin(identity) : null;
        const displayName = plugin ? String(plugin.displayName || plugin.name || '').trim() : '';
        const value = displayName ? this.#host.formatPluginName(displayName) : identity ? this.#host.formatPluginName(identity) : i18n.t('common.notAvailableShort');
        const label = i18n.t('plugins.stats.lastUsedPlugin');
        const signature = `${label}\n${value}`;
        if (signature === this.#lastUsedSignature) return false;
        this.#lastUsedSignature = signature;
        this.#host.updateHeaderStat('last-used-plugin', label, value);
        return true;
    }

    updateLastUsedStat(latestUsage?: LatestUsageResource): void {
        if (this.#applyLastUsedStat(latestUsage)) this.#host.queueResponsiveLayoutUpdate();
    }

    updateStopAllButtonVisibility(): void {
        const stopAllButton = this.#host.pageDom.optional(PLUGINS_ACTION_STOP_ALL);
        if (!stopAllButton) {
            return;
        }
        const plugins = this.#host.getCollectionPlugins();
        if (!plugins || !isArray(plugins)) {
            return;
        }
        const hasStoppable = plugins.some((plugin: PluginRecord): boolean => this.#host.isPluginStoppable(plugin));
        this.#host.pageDom.toggleClass(stopAllButton, this.#classes.hidden, !hasStoppable);
    }
}

export { PluginsStatsController };
export type { PluginsStatsControllerHost };
