/* SoAI - Settings instance identity view [frontend/assets/ts/pages/settings/controllers/instanceidentity/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { securityApi, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { createSettingsManualFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSettingItem, renderSettingsCodeValue, renderSettingsGroup, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';

const INSTANCE_NAME_FIELD_KEY = 'instance-name';
const INSTANCE_NAME_INPUT_ID = 'settings-instance-name';
const INSTANCE_NAME_MAX_LENGTH = 64;

const renderInstanceIdentity = (instanceId: string, instanceName: string | null): TrustedHtml => {
    const escapedName = securityApi.escapeAttribute(instanceName ?? '');
    const inputLabel = i18n.t('settings.instanceIdentity.name.label');
    const control = `<input type="text" id="${INSTANCE_NAME_INPUT_ID}" class="setting-input setting-input--wide" value="${escapedName}" maxlength="${String(INSTANCE_NAME_MAX_LENGTH)}" placeholder="${securityApi.escapeAttribute(i18n.t('settings.instanceIdentity.name.placeholder'))}" autocomplete="off" spellcheck="false" aria-label="${securityApi.escapeAttribute(inputLabel)}">`;
    return toTrustedUiHtml(
        renderSettingsSubgroup({
            title: i18n.t('settings.instanceIdentity.title'),
            description: i18n.t('settings.instanceIdentity.description'),
            content: renderSettingsGroup([
                renderSettingItem({
                    label: inputLabel,
                    help: i18n.t('settings.instanceIdentity.name.help'),
                    fieldKey: createSettingsManualFieldKey(INSTANCE_NAME_FIELD_KEY),
                    className: '',
                    control
                }),
                renderSettingItem({
                    label: i18n.t('settings.instanceIdentity.id.label'),
                    help: i18n.t('settings.instanceIdentity.id.help'),
                    className: 'settings-instance-id',
                    control: renderSettingsCodeValue(instanceId, undefined, 'u-line-clamp-2')
                })
            ])
        })
    );
};

export { INSTANCE_NAME_FIELD_KEY, INSTANCE_NAME_INPUT_ID, INSTANCE_NAME_MAX_LENGTH, renderInstanceIdentity };
