/* SoAI - Shared component support realtime lifecycle [frontend/assets/ts/core/componentsupport/realtimeLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ErrorWithName } from '@core/types/streamTypes.ts';

type RealtimeLifecycleHandlerKey = 'onInitial' | 'onUpdate' | 'onConnect' | 'onError' | 'onFirstError' | 'onReconnecting' | 'onReconnectFailed' | 'onStartError' | 'onFetchError' | 'onFetchSuccess' | 'onManagerUnavailable';
type RealtimeLifecycleArgument = Error | ErrorWithName | JsonValue | undefined;

const REALTIME_LIFECYCLE_HANDLER_KEYS: readonly RealtimeLifecycleHandlerKey[] = ['onInitial', 'onUpdate', 'onConnect', 'onError', 'onFirstError', 'onReconnecting', 'onReconnectFailed', 'onStartError', 'onFetchError', 'onFetchSuccess', 'onManagerUnavailable'];

interface RealtimeLifecycleHandlers {
    onWarningStateChange?: (warning: boolean, ...inputArguments: RealtimeLifecycleArgument[]) => void;
    onInitial?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onUpdate?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onConnect?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onError?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onFirstError?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onReconnecting?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onReconnectFailed?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onStartError?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onFetchError?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onFetchSuccess?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
    onManagerUnavailable?: (...inputArguments: RealtimeLifecycleArgument[]) => void;
}

export { REALTIME_LIFECYCLE_HANDLER_KEYS };
export type { RealtimeLifecycleArgument, RealtimeLifecycleHandlerKey, RealtimeLifecycleHandlers };
