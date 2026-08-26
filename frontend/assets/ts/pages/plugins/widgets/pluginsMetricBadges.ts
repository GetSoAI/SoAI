/* SoAI - Plugins page metric badges [frontend/assets/ts/pages/plugins/widgets/pluginsMetricBadges.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { formatUppercaseUnderscoreLabel } from '@core/primitives/text.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { isString } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

const MODELS_METRIC_BADGE_TYPE = 'MODELS';

const normalizeMetricBadgeType = (value: string): string => formatUppercaseUnderscoreLabel(value);

const resolvePluginsMetricBadgeType = (element: Element | null, optionalUi: (selector: string, context?: Element) => Element | null): string | null => {
    const badge = element?.closest('.ui-metric-badge, .ui-collection-list__fact');
    if (!badge || !(badge instanceof HTMLElement)) return null;
    const metricKey = badge.dataset?.['metricKey'];
    if (isString(metricKey) && metricKey) {
        return normalizeMetricBadgeType(metricKey);
    }
    const label = optionalUi('.ui-metric-label', badge);
    const text = label?.textContent?.trim();
    return text ? text.toUpperCase() : null;
};

const navigateFromPluginsMetricBadge = (badgeType: string | null, plugin: PluginRecord, router: Router | null): void => {
    if (badgeType !== MODELS_METRIC_BADGE_TYPE || !router) return;
    const pluginName = toTrimmedString(plugin.name);
    if (!pluginName) return;
    terminateHandledPromise(router.navigate({ path: 'models', parameters: { plugin: pluginName } }));
};

export { navigateFromPluginsMetricBadge, resolvePluginsMetricBadgeType };
