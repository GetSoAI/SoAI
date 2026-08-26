/* SoAI - Hardware page control layer render chart presentation controller [frontend/assets/ts/pages/hardware/controllers/render/hardwareChartPresentationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHistoryChartPresentation, type HistoryChartPresentation } from '@features/charts/public.ts';

type HardwareChartPresentationController = {
    beginLoad: () => number;
    completeLoad: (sequence: number) => void;
    reset: () => void;
    destroy: () => void;
};

const createHardwareChartPresentationController = (resolveHost: () => HTMLElement): HardwareChartPresentationController => {
    let presentation: HistoryChartPresentation | null = null;
    let activeSequence: number | null = null;

    const getPresentation = (): HistoryChartPresentation => {
        if (!presentation) {
            presentation = createHistoryChartPresentation(resolveHost());
        }
        return presentation;
    };

    return {
        beginLoad: (): number => {
            activeSequence = getPresentation().begin();
            return activeSequence;
        },
        completeLoad: (sequence: number): void => {
            if (activeSequence !== sequence) {
                return;
            }
            activeSequence = null;
            getPresentation().complete(sequence);
        },
        reset: (): void => {
            activeSequence = null;
            getPresentation().reset();
        },
        destroy: (): void => {
            activeSequence = null;
            getPresentation().destroy();
        }
    };
};

export { createHardwareChartPresentationController };
export type { HardwareChartPresentationController };
