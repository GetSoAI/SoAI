/* SoAI - Updates page public contracts [frontend/assets/ts/pages/updates/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export type UpdatesPageNoticeTone = 'grey' | 'green' | 'blue' | 'orange' | 'red';

export interface NormalizedUpdatePayload {
    updateAvailable: boolean;
    currentVersion: string;
    latestVersion: string;
    message: string;
    releaseUrl: string;
    releaseNotes: string;
    publishedAt: string;
}

export interface UpdatesUiRefs {
    pageNotice: HTMLElement;
    pageNoticeIndicator: HTMLElement;
    pageNoticeHeading: HTMLElement;
    pageNoticeDetail: HTMLElement;
    statusIcon: HTMLElement;
    statusSpinner: HTMLElement;
    statusHeading: HTMLElement;
    statusDetail: HTMLElement;
    detailsSection: HTMLElement;
    summaryContainer: HTMLElement;
    notesContainer: HTMLElement;
    notesBody: HTMLElement;
}
