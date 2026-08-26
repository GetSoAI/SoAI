/* SoAI - Shared client data hub actions [frontend/assets/ts/core/data/clientdatahub/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceDiff } from '@core/data/clientdatahub/types.ts';

const createEmptyDiff = (): ResourceDiff => {
    return { added: [], updated: [], removed: [] };
};

export { createEmptyDiff };
