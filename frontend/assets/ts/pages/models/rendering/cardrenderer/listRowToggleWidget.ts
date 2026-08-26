/* SoAI - Models page list row toggle widget [frontend/assets/ts/pages/models/rendering/cardrenderer/listRowToggleWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderActionToggleSwitch } from '@core/toggleSwitch.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { MODELS_ACTION_TOGGLE_ENABLED } from '@pages/models/actions.ts';
import type { ModelCardHost } from '@pages/models/rendering/cardrenderer/types.ts';

const isModelListToggleChecked = (model: ModelData): boolean => model.isEnabled !== false;

const buildModelListEnabledToggle = (model: ModelData, host: ModelCardHost): string => {
    const checked = isModelListToggleChecked(model);
    const label = checked ? i18n.t('common.enabled') : i18n.t('common.disabled');
    const pendingTarget = host.status.getPendingToggleTarget(model);
    const pending = pendingTarget === true || pendingTarget === false;
    return renderActionToggleSwitch({
        action: MODELS_ACTION_TOGGLE_ENABLED,
        checked,
        label,
        wrapperTag: 'label',
        wrapperClassName: 'model-enable-toggle ui-collection-card__toggle',
        inputClassName: 'model-enable-checkbox',
        labelClassName: 'model-enable-label ui-collection-card__toggle-label toggle-label',
        pending
    });
};

export { buildModelListEnabledToggle, isModelListToggleChecked };
