/* SoAI - Shared realtime detached task payload [frontend/assets/ts/core/realtime/streammanager/actions/detachedTaskPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

const buildDetachedTaskPayload = (taskId: string): JsonObject => {
    return {
        type: 'TaskDetachedEvent',
        taskId,
        status: 'detached',
        detached: true
    };
};

export { buildDetachedTaskPayload };
