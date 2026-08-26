/* SoAI - Frontend application loader [frontend/assets/ts/app/entrypoints/loader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { EntryName } from '@app/entrypoints/entrypoints.ts';
import type { EntryModule } from '@app/entrypoints/types.ts';
import { startDetachedWindow, startPrimaryApp } from '@app/entrypoints/service.ts';
import { isFunction } from '@core/typeGuards.ts';

const loadEntryDependencies = async (_entry: EntryName): Promise<EntryModule> => {
    if (!isFunction(startPrimaryApp) || !isFunction(startDetachedWindow)) {
        throw new Error('Invalid entry module structure: missing required entry point functions');
    }
    return { startPrimaryApp, startDetachedWindow };
};

export { loadEntryDependencies };
