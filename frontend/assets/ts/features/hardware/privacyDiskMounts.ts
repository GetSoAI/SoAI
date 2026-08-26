/* SoAI - Hardware feature privacy disk mounts [frontend/assets/ts/features/hardware/privacyDiskMounts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isSoAIInstallPath } from '@features/hardware/privacyInstallPaths.ts';

const normalizeWindowsDiskMountPath = (mountPath: string): string | null => {
    const driveRootMatch = /^([A-Za-z]):\\?$/.exec(mountPath);
    if (driveRootMatch) {
        const driveLetter = driveRootMatch[1];
        if (!driveLetter) throw new Error('normalizeWindowsDiskMountPath requires a drive letter');
        return `${driveLetter.toUpperCase()}:\\`;
    }
    const drivePathMatch = /^([A-Za-z]):\\(.+)$/.exec(mountPath);
    if (drivePathMatch) {
        const driveLetter = drivePathMatch[1];
        const pathTail = drivePathMatch[2];
        if (!driveLetter || !pathTail) throw new Error('normalizeWindowsDiskMountPath requires a drive path');
        const normalizedDrive = driveLetter.toUpperCase();
        const lowerTail = pathTail.toLowerCase();
        if (lowerTail.startsWith('users\\')) return `${normalizedDrive}:\\Users\\[user]`;
        if (lowerTail.startsWith('windows\\')) return `${normalizedDrive}:\\Windows\\[system]`;
        if (lowerTail.startsWith('program files\\')) return `${normalizedDrive}:\\Program Files\\[system]`;
        if (lowerTail.startsWith('program files (x86)\\')) return `${normalizedDrive}:\\Program Files (x86)\\[system]`;
        if (lowerTail.startsWith('programdata\\')) return `${normalizedDrive}:\\ProgramData\\[system]`;
        if (lowerTail.startsWith('system volume information\\')) return `${normalizedDrive}:\\System Volume Information\\[system]`;
        return `${normalizedDrive}:\\[mount]`;
    }
    if (mountPath.startsWith('\\\\')) return '\\\\[server]\\[share]';
    return null;
};

const normalizeMacDiskMountPath = (mountPath: string): string | null => {
    if (mountPath === '/Applications') return '/Applications';
    if (mountPath === '/Library') return '/Library';
    if (mountPath.startsWith('/Library/')) return '/Library/[system]';
    if (mountPath === '/Network') return '/Network';
    if (mountPath.startsWith('/Network/')) return '/Network/[share]';
    if (mountPath === '/System') return '/System';
    if (mountPath.startsWith('/System/')) return '/System/[system]';
    if (mountPath === '/private') return '/private';
    if (mountPath.startsWith('/private/')) return '/private/[system]';
    if (mountPath === '/var') return '/var';
    if (mountPath.startsWith('/var/')) return '/var/[system]';
    return null;
};

const normalizeDiskMountPath = (mountPath: string): string => {
    if (isSoAIInstallPath(mountPath)) return mountPath;
    const windowsMountPath = normalizeWindowsDiskMountPath(mountPath);
    if (windowsMountPath !== null) return windowsMountPath;
    const macMountPath = normalizeMacDiskMountPath(mountPath);
    if (macMountPath !== null) return macMountPath;
    if (mountPath === '/') return '/';
    if (mountPath === '/tmp') return '/tmp';
    if (mountPath === '/sys') return '/sys';
    if (mountPath.startsWith('/sys/')) return '/sys/[system]';
    if (mountPath === '/proc') return '/proc';
    if (mountPath.startsWith('/proc/')) return '/proc/[system]';
    if (mountPath === '/dev') return '/dev';
    if (mountPath.startsWith('/dev/')) return '/dev/[device]';
    if (mountPath === '/run') return '/run';
    if (mountPath.startsWith('/run/docker/netns/')) return '/run/docker/netns/[netns]';
    if (mountPath.startsWith('/run/user/')) return '/run/user/[user]';
    if (mountPath.startsWith('/run/credentials/')) return '/run/credentials/[service]';
    if (mountPath.startsWith('/run/')) return '/run/[runtime]';
    if (mountPath.startsWith('/boot/')) return '/boot/[boot]';
    if (mountPath.startsWith('/mnt/')) return '/mnt/[mount]';
    if (mountPath.startsWith('/media/')) return '/media/[user]/[volume]';
    if (mountPath.startsWith('/Volumes/')) return '/Volumes/[volume]';
    if (mountPath.startsWith('/home/')) return '/home/[user]';
    if (mountPath.startsWith('/Users/')) return '/Users/[user]';
    return '/[mount]';
};

export { normalizeDiskMountPath };
