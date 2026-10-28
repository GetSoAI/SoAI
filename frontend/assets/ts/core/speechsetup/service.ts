/* SoAI - Speech setup service resolution [frontend/assets/ts/core/speechsetup/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveKernelService, resolveOptionalKernelService } from '@core/runtime/runtimeContext.ts';
import type { SpeechSetupProtocol, SpeechSetupReason, SpeechSetupScope } from '@core/speechsetup/protocols.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';

const isSpeechSetup = <Value>(value: Value): value is Value & SpeechSetupProtocol => isObject(value) && hasFunctionProperty(value, 'snapshot') && hasFunctionProperty(value, 'ensureReady') && hasFunctionProperty(value, 'subscribe');

const requireSpeechSetup = (): SpeechSetupProtocol => {
    const service = resolveKernelService('core.speechSetup');
    if (!isSpeechSetup(service)) throw new Error('core.speechSetup is required');
    return service;
};

const resolveObservedSpeechReason = (reason: SpeechSetupReason | null, scope: SpeechSetupScope): SpeechSetupReason | null => {
    if (reason !== null) return reason;
    const service = resolveOptionalKernelService('core.speechSetup');
    if (!isSpeechSetup(service)) return null;
    const snapshot = service.snapshot(scope);
    return snapshot.fresh ? snapshot.reason : null;
};

export { requireSpeechSetup, resolveObservedSpeechReason };
