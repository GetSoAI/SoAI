/* SoAI - Chat feature tool activity status [frontend/assets/ts/features/chat/toolactivity/toolActivityStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import type { ToolActivityStatus } from '@features/chat/ChatTypes.ts';

const isToolActivityStatus = (value: JsonValue | undefined): value is ToolActivityStatus => {
    return isString(value) && (value === 'pending' || value === 'running' || value === 'completed' || value === 'cancelled' || value === 'error');
};

const resolveToolActivityStatusRank = (status: ToolActivityStatus): number => {
    if (status === 'pending') {
        return 0;
    }
    if (status === 'running') {
        return 1;
    }
    if (status === 'completed') {
        return 2;
    }
    if (status === 'cancelled') {
        return 3;
    }
    return 4;
};

export { isToolActivityStatus, resolveToolActivityStatusRank };
