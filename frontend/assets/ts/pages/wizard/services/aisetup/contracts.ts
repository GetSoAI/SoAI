/* SoAI - Wizard AI setup operation host contracts [frontend/assets/ts/pages/wizard/services/aisetup/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageStreamingContract } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { AiSetupFacts } from '@pages/wizard/services/aisetup/facts/service.ts';

interface AiSetupOperationsManagerHost {
    streaming: PageStreamingContract;
    getSetup(): AiSetupState;
    updateSetup(update: (setup: AiSetupState) => AiSetupState): void;
    getFacts(): AiSetupFacts | null;
    getModels(): readonly ModelData[];
    onEngineInstalled(pluginName: string): Promise<void>;
    onChange(): void;
    notify(message: string, type: NotificationType): void;
}

export type { AiSetupOperationsManagerHost };
