/* SoAI - Model detail page control layer parameter view manager constants [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ParameterGroup, ParameterView } from '@pages/modeldetail/contracts/parameterTypes.ts';

const FILTER_ALL_VALUE = 'all';
const FILTER_GROUP_PREFIX = 'group:';

const PARAMETERS_INTERFACE_ID = 'parameters-interface';
const PARAMETERS_EMPTY_STATE_ID = 'modeldetail-parameters-empty';

const PARAMETER_ITEM_SELECTOR = '.model-parameter-item[data-param]';
const PARAMETER_CATEGORY_SELECTOR = '.parameter-category';
const PARAMETER_CUSTOM_BADGE_SELECTOR = '.param-badge.custom';
const PARAMETER_REVERT_SELECTOR = '.model-parameter-revert';
const CATEGORY_COUNT_SELECTOR = '.param-count';

const PARAMETER_VIEWS: readonly ParameterView[] = ['all', 'customized', 'unsaved'];

const isParameterView = (value: string | null | undefined): value is ParameterView => PARAMETER_VIEWS.some((view) => view === value);

const PARAMETER_GROUPS: readonly ParameterGroup[] = ['startup', 'inference'];

const isParameterGroup = (value: string | null | undefined): value is ParameterGroup => PARAMETER_GROUPS.some((group) => group === value);

export { CATEGORY_COUNT_SELECTOR, FILTER_ALL_VALUE, isParameterGroup, isParameterView, PARAMETER_GROUPS, PARAMETER_VIEWS, FILTER_GROUP_PREFIX, PARAMETER_CATEGORY_SELECTOR, PARAMETER_CUSTOM_BADGE_SELECTOR, PARAMETER_ITEM_SELECTOR, PARAMETER_REVERT_SELECTOR, PARAMETERS_EMPTY_STATE_ID, PARAMETERS_INTERFACE_ID };
