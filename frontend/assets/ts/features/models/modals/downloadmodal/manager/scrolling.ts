/* SoAI - Download modal scroll targeting helpers [frontend/assets/ts/features/models/modals/downloadmodal/manager/scrolling.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';

const scrollDownloadModalSectionIntoView = (runtime: DownloadModalManagerRuntime, token: string): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const sectionElement = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, token), modalRoot);
    dom.flush();
    scrollElementIntoView(sectionElement, { block: 'start' });
};

export { scrollDownloadModalSectionIntoView };
