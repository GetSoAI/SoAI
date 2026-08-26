/* SoAI - Hardware feature models constants [frontend/assets/ts/features/hardware/models/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export const NETWORK_IGNORED_PREFIXES: readonly string[] = Object.freeze(['lo', 'docker', 'veth', 'br', 'virbr', 'kube']);

export const DEFAULT_IGNORED_NETWORK_PREFIXES: readonly string[] = NETWORK_IGNORED_PREFIXES;
export const DEFAULT_IGNORED_FILESYSTEMS: readonly string[] = Object.freeze(['loop', 'squashfs', 'tmpfs', 'devtmpfs']);
export const DEFAULT_IGNORED_MOUNTS: readonly string[] = Object.freeze(['/snap', '/boot/efi', '/sys', '/dev', '/run']);
export const DEFAULT_MIN_VOLUME_CAPACITY_GB = 1;
