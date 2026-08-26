/* SoAI - Shared routing resource events [frontend/assets/ts/core/routing/pages/collections/resource/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { encodeSegment } from '@core/identifiers.ts';
import { isInstanceOf, isString } from '@core/typeGuards.ts';
import { dom } from '@core/dom/dom.ts';
import type { ModelInterface, RouterInterface } from '@core/routing/pages/collections/resource/types.ts';

const getMetricBadgeType = (element: Element | null): string | null => {
    const badge = element?.closest('.ui-metric-badge, .ui-collection-list__fact');
    if (!badge) return null;

    if (!isInstanceOf(badge, HTMLElement)) {
        throw new TypeError('Metric badge must be an HTMLElement');
    }

    const metricKey = badge.dataset['metricKey'];
    if (metricKey) {
        return metricKey.toUpperCase().replace(/_/g, ' ').trim();
    }

    const label = dom.resolve('.ui-metric-label', badge)?.textContent?.trim();
    return label ? label.toUpperCase() : null;
};

const isMetricBadgeClick = (element: Element | null, targetType: string): boolean => {
    return getMetricBadgeType(element) === targetType;
};

const resolveModelId = (model: ModelInterface): string | null => {
    const universalIdValue = model.universalId;
    if (isString(universalIdValue) && universalIdValue.trim()) {
        return universalIdValue.trim();
    }
    const idValue = model['id'];
    if (isString(idValue) && idValue.trim()) {
        return idValue.trim();
    }
    if (typeof idValue === 'number' && Number.isFinite(idValue)) {
        return String(idValue);
    }
    return null;
};

const handleMetricBadgeNavigation = (element: Element | null, model: ModelInterface, router: RouterInterface | null): boolean => {
    const badgeType = getMetricBadgeType(element);
    if (!badgeType || !router) return false;

    const navigationMap: Record<string, () => void> = {
        PARAMETERS: () => {
            const id = resolveModelId(model);
            if (id) {
                void router.navigate(`model/${encodeSegment(id)}?tab=parameters`);
            }
        },
        'MODEL SIZE': () => {
            const id = resolveModelId(model);
            if (id) {
                void router.navigate(`model/${encodeSegment(id)}`);
            }
        },
        TOKENS: () => void router.navigate('metrics'),
        REQUESTS: () => void router.navigate('metrics'),
        MODELS: () => void router.navigate('models')
    };

    const handler = navigationMap[badgeType];
    if (!handler) return false;
    handler();
    return true;
};

export { getMetricBadgeType, handleMetricBadgeNavigation, isMetricBadgeClick };
