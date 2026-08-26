/* SoAI - Prompts page services service [frontend/assets/ts/pages/prompts/services/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatIsoTimestampForFilename } from '@core/time/localCalendar.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import { DATE_GROUP_KEYS, DEFAULT_GROUP_KEY, DOWNLOAD_SELECTION_PREFIX } from '@pages/prompts/contracts/constants.ts';
import type { ColorToolkitInterface, GroupResolvers, PromptGroup } from '@pages/prompts/contracts/contracts.ts';
import { mapPromptsByColor, mapPromptsByDate, mapPromptsByName, sanitizeFilenameCandidate } from '@pages/prompts/mappers/mappers.ts';
import { computePromptStats, type PromptStats } from '@pages/prompts/mappers/promptStatsDomain.ts';

interface DataAdapterOptions {
    colorToolkit: ColorToolkitInterface;
    downloadPrefix?: string;
}

class PromptDataAdapter {
    colorToolkit: ColorToolkitInterface;
    downloadPrefix: string;
    groupResolvers: Readonly<GroupResolvers>;

    constructor({ colorToolkit, downloadPrefix = DOWNLOAD_SELECTION_PREFIX }: DataAdapterOptions) {
        if (!colorToolkit?.normalize) {
            throw new Error('Prompts data adapter requires a color toolkit');
        }
        this.colorToolkit = colorToolkit;
        this.downloadPrefix = downloadPrefix;
        this.groupResolvers = Object.freeze(this.#createGroupResolvers());
    }

    getGroupResolvers(): Readonly<GroupResolvers> {
        return this.groupResolvers;
    }

    #createGroupResolvers(): GroupResolvers {
        return {
            [DEFAULT_GROUP_KEY]: (list: PromptRecord[]): PromptGroup[] => {
                if (!Array.isArray(list)) {
                    throw new TypeError('Group resolver list must be an array');
                }
                return [{ heading: null, prompts: list }];
            },
            date: (prompts: PromptRecord[]): PromptGroup[] => mapPromptsByDate(prompts, new Date(), DATE_GROUP_KEYS),
            name: mapPromptsByName,
            color: (prompts: PromptRecord[]): PromptGroup[] => mapPromptsByColor(prompts, this.colorToolkit)
        };
    }

    buildSelectionDownloadFilename(): string {
        const timestamp = formatIsoTimestampForFilename();
        const prefix = sanitizeFilenameCandidate(this.downloadPrefix, 'prompts').replace(/\s+/g, '-');
        return `${prefix}-${timestamp}.txt`;
    }

    buildPromptFilename(name: string | null): string {
        const fallback = i18n.t('prompts.unnamedPrompt');
        return `${sanitizeFilenameCandidate(name || fallback, fallback)}.txt`;
    }

    computeStats(prompts: PromptRecord[], selectionSize = 0): PromptStats {
        return computePromptStats(prompts, this.colorToolkit, selectionSize);
    }
}

export { PromptDataAdapter };
