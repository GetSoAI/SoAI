/* SoAI - Frontend power action contracts [frontend/assets/ts/features/power/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type PowerActionId = 'restartApplication' | 'shutdownApplication' | 'rebootSystem' | 'shutdownSystem' | 'suspendSystem' | 'hibernateSystem';

const POWER_ACTION_IDS: ReadonlyArray<PowerActionId> = Object.freeze(['restartApplication', 'shutdownApplication', 'rebootSystem', 'shutdownSystem', 'suspendSystem', 'hibernateSystem']);
export { POWER_ACTION_IDS };
export type { PowerActionId };
