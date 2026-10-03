/* SoAI - Hardware page realtime state [frontend/assets/ts/pages/hardware/controllers/realtime/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { HistorySession } from '@features/charts/public.ts';
import type { HistorySnapshot } from '@features/hardware/public.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';

class HardwareHistorySession {
    readonly lifecycle = new HistorySession<HardwarePageSnapshot>();
    backup: HistorySnapshot | null = null;
    clearedThroughMs = 0;

    invalidate(): void {
        this.lifecycle.invalidate();
        this.backup = null;
    }
}

export { HardwareHistorySession };
