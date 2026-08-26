/* SoAI - Updates page boundary contracts [frontend/assets/ts/pages/updates/contracts/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { SetButtonLoadingOptions } from '@core/state/UIStateManager.ts';
import type { UpdatesEditionContribution } from '@core/edition/updatesContribution.ts';

interface RestartOverlayService {
    show(value: string): void;
}

interface UpdatesPageDependencies {
    restartOverlay: RestartOverlayService;
    product: UpdatesEditionContribution | null;
}

interface UpdatesStateManager {
    setButtonLoading?: ((target: HTMLElement, loading: boolean, options?: SetButtonLoadingOptions) => void) | undefined;
}

const isUpdatesStateManager = <T>(value: T): value is T & UpdatesStateManager => {
    if (!isObject(value)) {
        return false;
    }
    return !('setButtonLoading' in value) || value.setButtonLoading === undefined || hasFunctionProperty(value, 'setButtonLoading');
};

export { type UpdatesPageDependencies, type RestartOverlayService, isUpdatesStateManager };
