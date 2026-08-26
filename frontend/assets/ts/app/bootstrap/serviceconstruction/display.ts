/* SoAI - Frontend application display [frontend/assets/ts/app/bootstrap/serviceconstruction/display.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MainStateIndicatorComponent } from '@features/indicators/MainState.ts';
import { LiveStatusOverlay } from '@features/indicators/service.ts';
import { LayoutHeader } from '@core/layout/header/Header.ts';
import { LayoutSidebar } from '@core/layout/sidebar/Sidebar.ts';
import { CountdownOverlay } from '@features/overlays/Countdown.ts';

interface BootstrapDisplayServices {
    overlay: LiveStatusOverlay;
    mainStateIndicatorComponent: MainStateIndicatorComponent;
    countdownOverlay: CountdownOverlay;
    header: LayoutHeader;
    sidebarComponent: LayoutSidebar;
}

const createBootstrapDisplayServices = (): BootstrapDisplayServices => {
    return {
        overlay: new LiveStatusOverlay(),
        mainStateIndicatorComponent: new MainStateIndicatorComponent(),
        countdownOverlay: new CountdownOverlay(),
        header: new LayoutHeader(),
        sidebarComponent: new LayoutSidebar()
    };
};

export { createBootstrapDisplayServices };
