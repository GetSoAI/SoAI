/* SoAI - Frontend application phases [frontend/assets/ts/app/bootstrap/stages/phases.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BootstrapPhase } from '@app/bootstrap/stages/types.ts';

let bootstrapPhase: BootstrapPhase = 'prime';

const setBootstrapPhase = (phase: BootstrapPhase): void => {
    if (bootstrapPhase !== phase) {
        bootstrapPhase = phase;
    }
};

const getBootstrapPhase = (): BootstrapPhase => bootstrapPhase;

export { getBootstrapPhase, setBootstrapPhase };
