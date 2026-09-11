/* SoAI - Shared API UI paths [frontend/assets/ts/core/api/endpoints/uiPaths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MODELS_BASE_PATH } from '@core/api/endpoints/models.ts';
import { encodeSegment } from '@core/identifiers.ts';

const stopAllPluginsActionPath = (): string => '/api/v1/actions/stop-all-plugins';
const pluginActionPath = (pluginName: string, action: string): string => `/api/v1/actions/plugins/${encodeSegment(pluginName)}/${encodeSegment(action)}`;
const stopPluginActionPath = (pluginName: string): string => pluginActionPath(pluginName, 'stop');
const enablePluginActionPath = (pluginName: string): string => pluginActionPath(pluginName, 'enable');
const disablePluginActionPath = (pluginName: string): string => pluginActionPath(pluginName, 'disable');
const pluginDeletePath = (pluginName: string): string => `/api/v1/plugins/${encodeSegment(pluginName)}`;
const pluginLogoPath = (pluginName: string, revision: string): string => ['/api/v1/plugins', encodeSegment(pluginName), 'logo', `${encodeSegment(revision)}.png`].join('/');
const pluginClonePath = (pluginName: string): string => `/api/v1/plugins/${encodeSegment(pluginName)}/clone`;
const pluginDownloadPath = (): string => '/api/v1/plugins/download';
const pluginUploadPath = (): string => '/api/v1/plugins/upload';
const modelPath = (modelId: string): string => `${MODELS_BASE_PATH}/${encodeSegment(modelId)}`;
const notificationsPath = (): string => '/api/v1/webui/notifications';
const notificationsMarkReadPath = (): string => '/api/v1/webui/notifications/mark-read';
const notificationPath = (notificationId: string): string => `${notificationsPath()}/${encodeSegment(notificationId)}`;
const notificationOpenPath = (notificationId: string): string => `${notificationPath(notificationId)}/open`;

export { disablePluginActionPath, enablePluginActionPath, modelPath, notificationOpenPath, notificationPath, notificationsMarkReadPath, notificationsPath, pluginClonePath, pluginDeletePath, pluginDownloadPath, pluginLogoPath, pluginUploadPath, stopAllPluginsActionPath, stopPluginActionPath };
