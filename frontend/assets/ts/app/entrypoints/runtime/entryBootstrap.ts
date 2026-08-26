/* SoAI - Frontend application entry bootstrap [frontend/assets/ts/app/entrypoints/runtime/entryBootstrap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { bootstrapEntry } from '@app/entrypoints/runtime/entryLoader.ts';
import { selectFrontendEditionComposition, type FrontendEditionComposition } from '@app/edition/frontendEditionComposition.ts';
import { getLanguageService } from '@core/languageservice/service.ts';

export const startSoaiEntry = async (entry: string, composition: FrontendEditionComposition): Promise<void> => {
    const normalizedEntry = assertNonEmptyString(entry, 'runtime entry identifier');
    selectFrontendEditionComposition(composition);
    getLanguageService().configureCatalogs(composition.translationCatalogs);
    await bootstrapEntry({ entry: normalizedEntry });
};
