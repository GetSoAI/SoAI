/* SoAI - Settings speech-to-text model view [frontend/assets/ts/pages/settings/controllers/speechmodel/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { renderSettingItem, renderSettingsGroup, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderSpeechModelSelector } from '@core/speechsetup/modelSelector.ts';
import { renderSpeechSetupPlaceholder, SPEECH_MODEL_SETTING_PATH } from '@core/speechsetup/presentation.ts';
import type { ModelData } from '@core/types/modelTypes.ts';

const SPEECH_MODEL_SETTINGS_ID = 'settings-speech-model';
const SPEECH_MODEL_INPUT_ID = 'settings-speech-model-select';

const renderSpeechModelSettings = (savedValue: string, models: readonly ModelData[]): TrustedHtml =>
    toTrustedUiHtml(
        renderSettingsSubgroup({
            title: i18n.t('settings.speechToText.title'),
            description: i18n.t('settings.speechToText.description'),
            attributes: { id: SPEECH_MODEL_SETTINGS_ID },
            content: renderSettingsGroup([
                renderSettingItem({
                    label: i18n.t('settings.speechToText.model.label'),
                    help: i18n.t('settings.speechToText.model.help'),
                    className: 'speech-model-setting',
                    dataset: { path: SPEECH_MODEL_SETTING_PATH },
                    control: renderSpeechModelSelector(SPEECH_MODEL_INPUT_ID, SPEECH_MODEL_SETTING_PATH, savedValue, models),
                    footer: renderSpeechSetupPlaceholder(false, 'settings').html
                })
            ])
        })
    );

export { renderSpeechModelSettings, SPEECH_MODEL_INPUT_ID, SPEECH_MODEL_SETTINGS_ID };
