/* SoAI - Frontend connection status public surface [frontend/assets/ts/core/connectionstatus/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { ConnectionStatus, CONNECTION_STATUS_SERVICE_ID, createConnectionStatus, getConnectionStatus, requireConnectionStatus } from '@core/connectionstatus/connectionStatusRegistry.ts';
export type { ConnectionEvent, RestartInfo, RestartSubscriber, StatusSnapshot, StatusSubscriber, SystemInfo } from '@core/connectionstatus/connectionStatusRegistry.ts';
