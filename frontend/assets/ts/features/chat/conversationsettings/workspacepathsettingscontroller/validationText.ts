/* SoAI - Chat conversation workspace-path validation text [frontend/assets/ts/features/chat/conversationsettings/workspacepathsettingscontroller/validationText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ConversationWorkspacePathConfig } from '@features/chat/conversationsettings/settingsModels.ts';

const resolveWorkspacePathInvalidStatusText = (config: ConversationWorkspacePathConfig): string => {
    const validationCode = config.validationCode ? config.validationCode.trim() : '';
    if (validationCode === 'outside_root') {
        return i18n.t('chat.configuration.filesFolder.revokedHint');
    }
    if (validationCode === 'not_directory') {
        return i18n.t('chat.configuration.filesFolder.notDirectoryHint');
    }
    if (validationCode === 'invalid_default_root') {
        return i18n.t('chat.configuration.filesFolder.invalidDefaultHint');
    }
    if (config.validationMessage) {
        return config.validationMessage;
    }
    return i18n.t('chat.configuration.filesFolder.invalidHint');
};

export { resolveWorkspacePathInvalidStatusText };
