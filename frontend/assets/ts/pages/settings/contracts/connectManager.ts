/* SoAI - SoAI Connect settings manager capability contract [frontend/assets/ts/pages/settings/contracts/connectManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConnectPairingResponse } from '@core/api/contracts/systemConnectPairingContracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

interface ConnectBrowserOrigin {
    readonly protocol: string;
    readonly hostname: string;
    readonly port: string;
}

interface ConnectManagerPairingPort {
    load(options: { signal: AbortSignal }): Promise<ConnectPairingResponse>;
}

interface ConnectManagerPagePort {
    readBrowserOrigin(): ConnectBrowserOrigin;
    notify(message: string, type: NotificationType, duration?: number): void;
}

interface ConnectManagerViewPort {
    requireContainer(): Element;
    updateHtml(container: Element, markup: TrustedHtml): void;
    bindEvent(target: EventTarget, event: string, listener: (event: Event) => void): () => void;
    filter(): void;
    hasSearchQuery(): boolean;
}

interface ConnectManagerHost {
    pairing: ConnectManagerPairingPort;
    page: ConnectManagerPagePort;
    view: ConnectManagerViewPort;
}

export type { ConnectBrowserOrigin, ConnectManagerHost };
