/* SoAI - Model detail page rendering layer icons [frontend/assets/ts/pages/modeldetail/rendering/modelDetailIcons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIcon } from '@core/ui/icons/iconservice/public.ts';

type ModelDetailIconKey = 'PARAMETERS' | 'BACK' | 'FILTER' | 'CLOSE' | 'SEARCH' | 'MODIFIED' | 'RESET' | 'SAVE' | 'TEST' | 'ADD' | 'ALIAS' | 'INFERENCE' | 'DELETE' | 'BACKEND_DOCUMENTATION';

const MODEL_DETAIL_ICON_DEFINITIONS: Record<ModelDetailIconKey, { name: IconName; size: number }> = {
    PARAMETERS: { name: 'parameters', size: 16 },
    BACK: { name: 'arrow-left', size: 16 },
    FILTER: { name: 'filter', size: 14 },
    CLOSE: { name: 'close', size: 14 },
    SEARCH: { name: 'search', size: 16 },
    MODIFIED: { name: 'modified', size: 14 },
    RESET: { name: 'close', size: 14 },
    SAVE: { name: 'save', size: 14 },
    TEST: { name: 'model-test', size: 14 },
    ADD: { name: 'add', size: 16 },
    ALIAS: { name: 'edit', size: 24 },
    INFERENCE: { name: 'send', size: 24 },
    DELETE: { name: 'close', size: 24 },
    BACKEND_DOCUMENTATION: { name: 'book-open', size: 14 }
};

const MODEL_DETAIL_ICON_KEYS: ModelDetailIconKey[] = ['PARAMETERS', 'BACK', 'FILTER', 'CLOSE', 'SEARCH', 'MODIFIED', 'RESET', 'SAVE', 'TEST', 'ADD', 'ALIAS', 'INFERENCE', 'DELETE', 'BACKEND_DOCUMENTATION'];

const loadModelDetailIcons = async (): Promise<Record<string, TrustedHtml>> => {
    const markup: Record<string, TrustedHtml> = {};
    const icons = await Promise.all(MODEL_DETAIL_ICON_KEYS.map((key) => getIcon(MODEL_DETAIL_ICON_DEFINITIONS[key].name, { size: MODEL_DETAIL_ICON_DEFINITIONS[key].size })));
    MODEL_DETAIL_ICON_KEYS.forEach((key, index) => {
        const iconMarkup = icons[index];
        if (!iconMarkup || !iconMarkup.html.trim()) {
            const iconName = MODEL_DETAIL_ICON_DEFINITIONS[key].name;
            throw new Error(`ModelDetailPage icon "${iconName}" resolved empty markup`);
        }
        markup[key] = iconMarkup;
    });
    return markup;
};

export { loadModelDetailIcons };
