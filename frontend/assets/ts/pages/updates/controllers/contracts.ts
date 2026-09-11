/* SoAI - Updates page controllers contracts [frontend/assets/ts/pages/updates/controllers/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { SetButtonLoadingOptions } from '@core/state/UIStateManager.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { RestartOverlayService } from '@pages/updates/contracts/contracts.ts';

type UpdatesNotificationType = 'success' | 'error' | 'info' | 'warning';

interface UpdatesControllerNoticeSurface {
    toggleHidden: (element: Element, hidden: boolean) => void;
    updateText: (element: Element, text: string) => void;
}

interface UpdatesControllerSharedSurface extends UpdatesControllerNoticeSurface {
    handleError: (error: Error, context: string, options?: { notify?: boolean }) => void;
    updateHTML: (element: Element, html: TrustedHtml, options?: { escape?: boolean }) => void;
    updateProperty: (element: Element, property: string, value: DomPropertyValue) => void;
    updateCheckerboard: () => void;
    sanitizeHtml: (value: string) => string;
    sanitizeAttribute: (value: string) => string;
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
}

interface UpdatesControllerSystemSurface extends UpdatesControllerSharedSurface {
    notify: (message: string, type?: UpdatesNotificationType) => void;
    setButtonLoading: (button: HTMLElement, isLoading: boolean, options?: SetButtonLoadingOptions) => void;
    sanitizeUrl: (value: string, options: { allowRelative: boolean; allowDataImage: boolean; allowBlob: boolean }) => string | null;
    showOverlay: RestartOverlayService['show'];
    resolveInstallButton: () => HTMLButtonElement | null;
    wait: (ms: number) => Promise<void>;
}

interface UpdatesControllerProductSurface extends UpdatesControllerSharedSurface {
    notify: (message: string, type: UpdatesNotificationType) => void;
    startTaskAction: (endpoint: string, options: Record<string, JsonValue>) => Promise<StreamActionHandle>;
}

interface UpdatesPageWorkflowSurface extends UpdatesControllerSharedSurface {
    notify: (message: string, type?: UpdatesNotificationType) => void;
    setButtonLoading: (button: HTMLElement, isLoading: boolean, options?: SetButtonLoadingOptions) => void;
    sanitizeUrl: (value: string, options: { allowRelative: boolean; allowDataImage: boolean; allowBlob: boolean }) => string | null;
    resolveInstallButton: () => HTMLButtonElement | null;
    wait: (ms: number) => Promise<void>;
    startTaskAction: (endpoint: string, options: Record<string, JsonValue>) => Promise<StreamActionHandle>;
}

export type { UpdatesControllerNoticeSurface, UpdatesControllerProductSurface, UpdatesControllerSystemSurface, UpdatesNotificationType, UpdatesPageWorkflowSurface };
