/* SoAI - WebUI identity mutation protocol contract [frontend/assets/ts/core/users/identityMutationContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const IDENTITY_MUTATION_DEADLINE_MS = 30_000;
const SESSION_ROTATION_POST_COMMIT_MIN_MS = 60_000;
const IDENTITY_MUTATION_NETWORK_ALLOWANCE_MS = 5_000;
const IDENTITY_MUTATION_FINAL_PROBE_MS = 5_000;
const IDENTITY_MUTATION_CLIENT_RECOVERY_MS = IDENTITY_MUTATION_DEADLINE_MS + SESSION_ROTATION_POST_COMMIT_MIN_MS + IDENTITY_MUTATION_NETWORK_ALLOWANCE_MS;
const IDENTITY_MUTATION_SERVER_HORIZON_MS = IDENTITY_MUTATION_CLIENT_RECOVERY_MS + IDENTITY_MUTATION_FINAL_PROBE_MS;

type IdentityMutationType = 'username_rename' | 'password_change';
type IdentityMutationFailureCode = 'incorrect_current_password' | 'username_unchanged' | 'username_conflict' | 'operation_id_conflict' | 'user_state_conflict' | 'identity_mutation_deadline_exceeded' | 'identity_mutation_cancelled' | 'identity_mutation_not_committed' | 'identity_mutation_time_invalid' | 'identity_mutation_session_collision' | 'identity_mutation_failed' | 'session_rotation_window_unavailable';

const IDENTITY_MUTATION_FAILURE_CODES: readonly IdentityMutationFailureCode[] = ['incorrect_current_password', 'username_unchanged', 'username_conflict', 'operation_id_conflict', 'user_state_conflict', 'identity_mutation_deadline_exceeded', 'identity_mutation_cancelled', 'identity_mutation_not_committed', 'identity_mutation_time_invalid', 'identity_mutation_session_collision', 'identity_mutation_failed', 'session_rotation_window_unavailable'];

const isIdentityMutationType = (value: string): value is IdentityMutationType => value === 'username_rename' || value === 'password_change';
const isIdentityMutationFailureCode = (value: string): value is IdentityMutationFailureCode => IDENTITY_MUTATION_FAILURE_CODES.some((code) => code === value);

export { IDENTITY_MUTATION_CLIENT_RECOVERY_MS, IDENTITY_MUTATION_DEADLINE_MS, IDENTITY_MUTATION_FAILURE_CODES, IDENTITY_MUTATION_FINAL_PROBE_MS, IDENTITY_MUTATION_NETWORK_ALLOWANCE_MS, IDENTITY_MUTATION_SERVER_HORIZON_MS, SESSION_ROTATION_POST_COMMIT_MIN_MS, isIdentityMutationFailureCode, isIdentityMutationType };
export type { IdentityMutationFailureCode, IdentityMutationType };
