/* SoAI - Hardware page controllers effects [frontend/assets/ts/pages/hardware/controllers/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { parseStandardNotificationType } from '@core/ui/notifications/notificationTypeParsing.ts';

interface HardwareOnShowDependencies {
    applySelectionFromQuery: () => boolean;
    scheduleChartBootstrap: (options: { force: boolean; resetView: boolean; signal?: AbortSignal | null }) => Promise<void>;
    signal?: AbortSignal | null;
}

const prepareHardwarePageContent = async (dependencies: HardwareOnShowDependencies): Promise<void> => {
    const changed = dependencies.applySelectionFromQuery();
    await dependencies.scheduleChartBootstrap({ force: changed, resetView: changed, signal: dependencies.signal ?? null });
};

const normalizeHardwareNotificationType = (value: string): NotificationType => parseStandardNotificationType(value);

export { normalizeHardwareNotificationType, prepareHardwarePageContent };
export type { HardwareOnShowDependencies };
