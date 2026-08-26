/* SoAI - Frontend automation model options [frontend/assets/ts/features/automation/modelOptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import { isLocalModelCatalogEntry, type ModelCatalogResponse } from '@core/api/contracts/modelCatalogContracts.ts';
import type { AutomationModelOption } from '@features/automation/contracts.ts';

const parseAutomationModelOptions = (value: ModelCatalogResponse): readonly AutomationModelOption[] => {
    const options: AutomationModelOption[] = [];
    const seenIds = new Set<string>();
    for (const [groupName, groupValue] of Object.entries(value)) {
        for (const entry of groupValue) {
            const isLocal = isLocalModelCatalogEntry(entry);
            const id = isLocal ? entry.universalId : entry.id;
            if (seenIds.has(id)) {
                throw new Error(`Model list contains a duplicate id: ${id}`);
            }
            seenIds.add(id);
            options.push({
                id,
                detailUniversalId: isLocal ? entry.universalId : null,
                label: entry.name,
                provider: isLocal ? entry.plugin : groupName,
                loaded: isLocal ? entry.isLoaded : true,
                available: isLocal ? entry.isAvailable : true
            });
        }
    }
    return options.sort((left, right) => left.label.localeCompare(right.label, getCurrentLocale()));
};

export { parseAutomationModelOptions };
