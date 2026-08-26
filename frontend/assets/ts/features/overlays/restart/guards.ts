/* SoAI - Overlays feature restart validation [frontend/assets/ts/features/overlays/restart/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isObject, isString } from '@core/typeGuards.ts';
import type { ApiInterface, DomInterface, OperationType } from '@features/overlays/restart/types.ts';

const OPERATION_TYPES: ReadonlySet<string> = new Set(['restart-application', 'system-reboot', 'system-shutdown', 'system-sleep', 'update-soai', 'restore-backup', 'connection-lost']);

const isOperationType = <Candidate>(value: Candidate): value is Candidate & OperationType => isString(value) && OPERATION_TYPES.has(value);

const isApiInterface = <T>(value: T): value is T & ApiInterface => {
    if (!isObject(value)) return false;
    if (!hasFunctionProperty(value, 'initialize')) return false;
    if (!('system' in value)) return false;
    const systemValue = value.system;
    return isObject(systemValue) && hasFunctionProperty(systemValue, 'health') && hasFunctionProperty(systemValue, 'status');
};

const isDomInterface = <T>(value: T): value is T & DomInterface => isObject(value) && hasFunctionProperty(value, 'querySafe');

export { isApiInterface, isDomInterface, isOperationType };
