// SoAI native Windows launcher and lifecycle ownership [SoAILauncher.cs]
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using Microsoft.Win32;
using Microsoft.Win32.SafeHandles;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Globalization;
using System.IO;
using System.IO.Pipes;
using System.Linq;
using System.Net;
using System.Net.Security;
using System.Runtime.CompilerServices;
using System.Runtime.ExceptionServices;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography.X509Certificates;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace SoAILauncher
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            AppContext.SetSwitch("Switch.System.IO.UseLegacyPathHandling", false);
            AppContext.SetSwitch("Switch.System.IO.BlockLongPaths", false);
            AppDomain domain = AppDomain.CurrentDomain;
            domain.SetData("APP_CONFIG_FILE", domain.SetupInformation.ApplicationName + ".config");
            PublicStopDeadline stopDeadline;
            string image;
            try
            {
                args = LauncherCommand.NormalizeCompleteInstallArguments(args);
                try { stopDeadline = PublicStopDeadline.FromCommand(ref args); }
                catch (ArgumentException)
                {
                    Console.Error.WriteLine("The Windows stop completion handoff is invalid. Retry stop from the installed launcher.");
                    return 1;
                }
                image = NativeBackendJob.ReadProcessImagePath(NativeBackendJob.GetCurrentProcess());
            }
            catch (Exception exception)
            {
                return ReportUnresolvedInstallation(args, exception);
            }
            if (SynchronousUninstall.IsCommand(image, args))
            {
                return SynchronousUninstall.Run(image, args);
            }
            if (args.Length > 0 && string.Equals(args[0], "--recover-install-lock", StringComparison.Ordinal))
            {
                try
                {
                    NativeConsole.UseStrictUtf8StandardStreams();
                    if (args.Length != 2 || !LauncherPaths.IsAbsoluteFilesystemPath(args[1]))
                    {
                        throw new ArgumentException("Install lock recovery requires one absolute lock directory.");
                    }
                    string retained = NativeFilesystemHandles.RecoverAbandonedInstallLock(args[1]);
                    if (retained != null) { Console.WriteLine(retained); }
                    return 0;
                }
                catch (Exception exception)
                {
                    Console.Error.WriteLine("Installation lock recovery failed: " + exception.Message);
                    return 1;
                }
            }
            if (UpdateProgressWindow.IsCommand(args))
            {
                return UpdateProgressWindow.Run(args);
            }
            LauncherPaths paths;
            try
            {
                paths = LauncherPaths.FromExecutable();
            }
            catch (Exception exception)
            {
                return ReportUnresolvedInstallation(args, exception);
            }
            try
            {
                NativeBackendJob.PrepareTemporaryEnvironment();
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                Console.Error.WriteLine("SoAI cannot use the Windows temporary directory. Choose an existing temporary directory supported by this host.");
                return 1;
            }
            if (BackendService.IsCommand(args))
            {
                return BackendService.Run(paths, args);
            }
            if (ServiceRegistration.IsCommand(args))
            {
                return ServiceRegistration.Run(args);
            }
            if (UpdateRecovery.IsRestorationCommand(args))
            {
                return UpdateRecovery.RunRestoration(paths, args);
            }
            if (LauncherCommand.IsElevatedConsoleHandoff(args))
            {
                if (!PrivilegeState.IsElevated())
                {
                    return 1;
                }
                try
                {
                    return RunConsoleCommand(paths, LauncherCommand.RemoveElevatedConsoleHandoff(args), stopDeadline);
                }
                catch (Exception exception)
                {
                    if (LauncherCommand.IsInstallCommand(LauncherCommand.RemoveElevatedConsoleHandoff(args)))
                    {
                        Console.Error.WriteLine("SoAI installation preparation failed: " + exception.Message);
                    }
                    else { LauncherDiagnostics.WriteStartupFailure(paths, exception); }
                    return 1;
                }
            }
            if (LauncherCommand.IsConsoleCommand(args))
            {
                NativeConsole.AttachOrCreate();
                if (LauncherCommand.RequiresAdministrator(args) && !PrivilegeState.IsElevated())
                {
                    return PrivilegeState.RunElevatedConsoleCommand(args, stopDeadline);
                }
                try
                {
                    return RunConsoleCommand(paths, args, stopDeadline);
                }
                catch (Exception ex)
                {
                    if (LauncherCommand.IsInstallCommand(args))
                    {
                        Console.Error.WriteLine("SoAI installation preparation failed: " + ex.Message);
                        return 1;
                    }
                    string diagnosticPath = LauncherDiagnostics.WriteStartupFailure(paths, ex);
                    Console.Error.WriteLine("SoAI launcher failed: " + ex.Message);
                    if (!string.IsNullOrWhiteSpace(diagnosticPath))
                    {
                        Console.Error.WriteLine("Full details were written to: " + diagnosticPath);
                    }
                    return 1;
                }
            }
            if (PrivilegeState.IsElevated())
            {
                if (UnelevatedLauncher.IsHandoffCommand(args))
                {
                    MessageBox.Show("SoAI could not enter the standard desktop session. Start SoAI from its desktop shortcut.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return 1;
                }
                return UnelevatedLauncher.TryLaunch(paths, image, args) ? 0 : 1;
            }
            try
            {
                args = UnelevatedLauncher.CompleteHandoff(args);
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                MessageBox.Show("SoAI could not complete the standard desktop handoff.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
            if (LauncherCommand.RemoveAfterUpdateArgument(args).Length > 0)
            {
                MessageBox.Show("SoAI does not accept start options. Its background service always starts with fixed settings. Start SoAI without options, or run soai.exe status, stop, restart, install, or version from a terminal.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 2;
            }
            return RunDesktop(paths, LauncherCommand.IsAfterUpdateLaunch(args));
        }

        private static int ReportUnresolvedInstallation(string[] args, Exception exception)
        {
            string diagnosticPath = LauncherDiagnostics.WriteStartupFailure(null, exception);
            string message = "SoAI could not verify its installed program file and folder. Repair SoAI with its installer, then start it again.";
            if (!string.IsNullOrWhiteSpace(diagnosticPath))
            {
                message += " Full details were written to: " + diagnosticPath;
            }
            if (LauncherCommand.IsConsoleCommand(args))
            {
                NativeConsole.AttachOrCreate();
            }
            Console.Error.WriteLine(message);
            if (!LauncherCommand.IsConsoleCommand(args) && Array.IndexOf(args, "/S") < 0)
            {
                MessageBox.Show(message, "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            return 1;
        }

        private static int RunConsoleCommand(LauncherPaths paths, string[] args, PublicStopDeadline stopDeadline)
        {
            if (stopDeadline != null) { return stopDeadline.Stop(paths, args); }
            int preparationExit = BackendProcess.PrepareInstallRuntime(paths, args);
            if (preparationExit != 0)
            {
                return preparationExit;
            }
            int exitCode = BackendProcess.RunForeground(paths, args);
            return exitCode == 0 && LauncherCommand.IsInstallDepsCommand(args) ? BackendProcess.CompleteInstallation(paths) : exitCode;
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static int RunDesktop(LauncherPaths paths, bool afterUpdate)
        {
            try
            {
                using (DesktopLauncherInstance instance = new DesktopLauncherInstance(paths.RootDirectory))
                {
                    if (!instance.AcquireOrActivate()) { return 0; }
                    return RunOwnedDesktop(paths, afterUpdate, instance);
                }
            }
            catch (Exception exception)
            {
                string diagnosticPath = LauncherDiagnostics.WriteStartupFailure(paths, exception);
                string message = exception is TimeoutException
                    ? "The existing SoAI window is still closing. Wait for it to finish, then start SoAI again."
                    : exception is UnauthorizedAccessException
                        ? "Windows denied access to SoAI's desktop session. Start SoAI from its shortcut using the same Windows account."
                        : "SoAI could not initialize its desktop window. Try starting SoAI again; if it still fails, repair SoAI with its installer.";
                if (!string.IsNullOrWhiteSpace(diagnosticPath)) { message += " Details: " + diagnosticPath; }
                MessageBox.Show(message,
                    "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static int RunOwnedDesktop(LauncherPaths paths, bool afterUpdate, DesktopLauncherInstance instance)
        {
            LoopbackCertificatePolicy.Install();
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (LauncherForm form = new LauncherForm(paths, afterUpdate))
            using (DesktopWindowSession session = new DesktopWindowSession(form, instance.BeginShutdown))
            {
                form.DesktopSession = session;
                instance.Attach(form, delegate { return form.CanActivateDesktop; }, session.RestoreMainWindow, delegate { form.ReleaseBackend(true); form.CloseQuietly(); });
                form.Show();
                Application.Run(session);
                return form.ExitCode;
            }
        }
    }

    internal sealed class DesktopLauncherInstance : IDisposable
    {
        private readonly Mutex ownership;
        private readonly EventWaitHandle activation;
        private readonly EventWaitHandle closing;
        private readonly EventWaitHandle stopRequested;
        private bool ownsDesktop;
        private System.Windows.Forms.Timer activationTimer;

        public DesktopLauncherInstance(string rootDirectory)
        {
            string account;
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent()) { account = identity.User.Value; }
            string name = "Local\\SoAI.Desktop." + account + "." + LauncherPaths.StableRootIdentity(rootDirectory);
            try
            {
                ownership = new Mutex(false, name + ".Owner");
                activation = new EventWaitHandle(false, EventResetMode.AutoReset, name + ".Activate");
                closing = new EventWaitHandle(false, EventResetMode.ManualReset, name + ".Closing");
                EventWaitHandleSecurity security = new EventWaitHandleSecurity();
                security.SetAccessRuleProtection(true, false);
                foreach (SecurityIdentifier identity in new SecurityIdentifier[] {
                    new SecurityIdentifier(account),
                    new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
                    new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null) })
                {
                    security.AddAccessRule(new EventWaitHandleAccessRule(identity, EventWaitHandleRights.FullControl, AccessControlType.Allow));
                }
                bool created;
                using (Process current = Process.GetCurrentProcess())
                {
                    stopRequested = new EventWaitHandle(false, EventResetMode.AutoReset, StopEventName(rootDirectory, current), out created, security);
                }
                if (!created) { throw new InvalidOperationException("The desktop stop channel is already owned; startup cannot verify its identity."); }
            }
            catch
            {
                Dispose();
                throw;
            }
        }

        public bool AcquireOrActivate()
        {
            Stopwatch deadline = Stopwatch.StartNew();
            while (true)
            {
                try { ownsDesktop = ownership.WaitOne(0); }
                catch (AbandonedMutexException) { ownsDesktop = true; }
                if (ownsDesktop)
                {
                    closing.Reset();
                    return true;
                }
                if (!closing.WaitOne(0))
                {
                    activation.Set();
                    if (!closing.WaitOne(0)) { return false; }
                }
                if (deadline.Elapsed >= TimeSpan.FromSeconds(10))
                {
                    throw new TimeoutException("The existing desktop launcher did not finish closing within ten seconds.");
                }
                Thread.Sleep(50);
            }
        }

        public void BeginShutdown()
        {
            closing.Set();
        }

        private static string StopEventName(string rootDirectory, Process process)
        {
            return "Global\\SoAI.Desktop.Stop." + LauncherPaths.StableRootIdentity(rootDirectory)
                + "." + process.Id.ToString(CultureInfo.InvariantCulture)
                + "." + process.StartTime.ToUniversalTime().ToFileTimeUtc().ToString("x16", CultureInfo.InvariantCulture);
        }

        internal static bool TryRequestStop(string rootDirectory, Process process)
        {
            try
            {
                using (EventWaitHandle request = EventWaitHandle.OpenExisting(StopEventName(rootDirectory, process), EventWaitHandleRights.Modify))
                {
                    request.Set();
                    return true;
                }
            }
            catch (WaitHandleCannotBeOpenedException)
            {
                return false;
            }
        }

        public void Attach(Form form, Func<bool> canActivate, Action restoreMainWindow, Action requestStop)
        {
            if (!ownsDesktop) { throw new InvalidOperationException("Desktop ownership is required before attaching a window."); }
            activationTimer = new System.Windows.Forms.Timer();
            activationTimer.Interval = 200;
            activationTimer.Tick += delegate
            {
                if (stopRequested.WaitOne(0)) { requestStop(); return; }
                if (!canActivate() || !activation.WaitOne(0)) { return; }
                restoreMainWindow();
                if (form.WindowState == FormWindowState.Minimized) { form.WindowState = FormWindowState.Normal; }
                form.Activate();
                if (!SetForegroundWindow(form.Handle)) { FlashWindow(form.Handle, true); }
            };
            activationTimer.Start();
        }

        public void Dispose()
        {
            if (activationTimer != null) { activationTimer.Dispose(); }
            if (ownsDesktop)
            {
                closing.Set();
                ownership.ReleaseMutex();
                ownsDesktop = false;
            }
            if (stopRequested != null) { stopRequested.Dispose(); }
            if (closing != null) { closing.Dispose(); }
            if (activation != null) { activation.Dispose(); }
            if (ownership != null) { ownership.Dispose(); }
        }

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetForegroundWindow(IntPtr window);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool FlashWindow(IntPtr window, bool invert);
    }

    internal sealed class DesktopWindowSession : ApplicationContext
    {
        private readonly Form mainWindow;
        private readonly Action beginShutdown;
        private readonly List<Form> detachedWindows = new List<Form>();

        public DesktopWindowSession(Form mainWindow, Action beginShutdown)
        {
            this.mainWindow = mainWindow;
            this.beginShutdown = beginShutdown;
            mainWindow.FormClosed += delegate { ExitThread(); };
        }

        public bool MainDismissed { get; private set; }
        public bool IsClosing { get; private set; }
        public Form[] DetachedWindows { get { return detachedWindows.ToArray(); } }

        public Form[] ReleaseDetachedWindows()
        {
            if (!IsClosing) { throw new InvalidOperationException("Detached windows can only be released during desktop shutdown."); }
            Form[] windows = detachedWindows.ToArray();
            detachedWindows.Clear();
            return windows;
        }

        public void RegisterDetachedWindow(Form window)
        {
            if (IsClosing) { throw new InvalidOperationException("The desktop session is closing."); }
            detachedWindows.Add(window);
            window.FormClosed += delegate
            {
                detachedWindows.Remove(window);
                CloseIfLastWindow();
            };
        }

        public bool TryDismissMainWindow(CloseReason reason)
        {
            if (IsClosing || reason != CloseReason.UserClosing || !HasDetachedPages()) { return false; }
            MainDismissed = true;
            mainWindow.Hide();
            return true;
        }

        public void RestoreMainWindow()
        {
            if (IsClosing) { return; }
            MainDismissed = false;
            mainWindow.Show();
        }

        public void BeginShutdown()
        {
            if (IsClosing) { return; }
            IsClosing = true;
            beginShutdown();
        }

        private bool HasDetachedPages()
        {
            return detachedWindows.Any(window => !window.IsDisposed && window.Visible && window.ShowInTaskbar);
        }

        private void CloseIfLastWindow()
        {
            if (!MainDismissed || IsClosing || HasDetachedPages()) { return; }
            BeginShutdown();
            mainWindow.Close();
        }
    }

    public static class SynchronousUninstall
    {
        private const string RecoveryArgument = "--soai-uninstall-root";
        private const string ProductKey = "Software\\SoAI";
        private const string UninstallKey = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\SoAI";
        private const string StageNamePrefix = ".SoAI-Uninstall-";
        private const string InstallationRootRecord = "installation-root.txt";
        private const string SuccessRecord = "success.txt";
        private const string SuccessRecordText = "Uninstall completed.";
        private const string StageRemovalLogPrefix = "soai-uninstall-stage-removal-";
        private const string StageRemovalReadyPrefix = "stage-removal-ready-";
        private const string StageRemovalFailurePrefix = "stage-removal-failure-";
        private const string PowerShellArguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass";
        private const int StageRemovalWaitMilliseconds = 60000;

        internal static bool IsCommand(string image, string[] args)
        {
            return string.Equals(Path.GetFileName(image), "Uninstall.exe", StringComparison.OrdinalIgnoreCase)
                || (args.Length > 0 && args[0] == RecoveryArgument);
        }

        public static bool OwnsWindowsIntegration(string root)
        {
            using (RegistryKey machine = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
            using (RegistryKey registration = machine.OpenSubKey(UninstallKey))
            {
                return registration != null && string.Equals(registration.GetValue("InstallLocation") as string, root, StringComparison.OrdinalIgnoreCase);
            }
        }

        internal static int Run(string image, string[] args)
        {
            string stage = null;
            LauncherPaths diagnosticPaths = null;
            List<SafeFileHandle> ancestors = new List<SafeFileHandle>();
            try
            {
                NativeBackendJob.PrepareTemporaryEnvironment();
                image = Path.GetFullPath(image);
                diagnosticPaths = LauncherPaths.FromRoot(Path.GetDirectoryName(image));
                string executableDirectory = diagnosticPaths.RootDirectory;
                image = Path.Combine(executableDirectory, Path.GetFileName(image));
                string root = executableDirectory;
                bool recovery = args.Length >= 2 && args[0] == RecoveryArgument;
                if (recovery)
                {
                    root = Path.GetFullPath(args[1]);
                    if (Directory.Exists(LauncherPaths.ToNativeFilesystemPath(root))) { root = LauncherPaths.FromRoot(root).RootDirectory; }
                    args = args.Skip(2).ToArray();
                    stage = executableDirectory;
                    ancestors.AddRange(NativeFilesystemHandles.RetainDirectoryAncestors(stage));
                    string recorded = File.ReadAllText(LauncherPaths.ToNativeFilesystemPath(Path.Combine(stage, InstallationRootRecord)), Encoding.UTF8);
                    if (!string.Equals(recorded, root, StringComparison.OrdinalIgnoreCase))
                    {
                        throw new InvalidOperationException("The uninstall recovery target does not match its retained evidence.");
                    }
                }
                if (args.Any(delegate(string argument) { return argument != "/S" && argument != "/REMOVEAPPDATA"; }))
                {
                    throw new ArgumentException("Uninstall accepts /S and /REMOVEAPPDATA.");
                }
                if (!PrivilegeState.IsElevated())
                {
                    ProcessStartInfo elevation = new ProcessStartInfo(image, BackendProcess.BuildArgumentString(
                        recovery ? new string[] { RecoveryArgument, root }.Concat(args).ToArray() : args));
                    elevation.UseShellExecute = true;
                    elevation.Verb = "runas";
                    using (Process elevated = Process.Start(elevation))
                    {
                        if (elevated == null || !elevated.WaitForExit(1800000)) { return 1; }
                        return elevated.ExitCode;
                    }
                }
                bool created;
                using (Mutex gate = new Mutex(false, "Global\\SoAI.WindowsInstaller.V1", out created))
                {
                    if (!created) { throw new InvalidOperationException("Another SoAI installer or uninstall operation is active."); }
                    {
                        string nativeRoot = LauncherPaths.ToNativeFilesystemPath(root);
                        ancestors.AddRange(NativeFilesystemHandles.RetainDirectoryAncestors(Path.GetDirectoryName(root)));
                        if (stage == null)
                        {
                            using (RegistryKey machine = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
                            using (RegistryKey registration = machine.OpenSubKey(UninstallKey))
                            {
                                if (registration != null && string.Equals(registration.GetValue("InstallLocation") as string, root, StringComparison.OrdinalIgnoreCase))
                                {
                                    string retained = registration.GetValue("SoAIRecoveryDirectory") as string;
                                    if (!string.IsNullOrWhiteSpace(retained))
                                    {
                                        RequireRegularFile(Path.Combine(retained, InstallationRootRecord));
                                        if (!string.Equals(File.ReadAllText(LauncherPaths.ToNativeFilesystemPath(Path.Combine(retained, InstallationRootRecord)), Encoding.UTF8), root, StringComparison.OrdinalIgnoreCase))
                                        {
                                            throw new InvalidOperationException("The uninstall recovery target conflicts with its retained evidence.");
                                        }
                                        stage = retained;
                                        ancestors.AddRange(NativeFilesystemHandles.RetainDirectoryAncestors(stage));
                                    }
                                }
                            }
                        }
                        if (stage == null)
                        {
                            List<SafeFileHandle> sources = NativeFilesystemHandles.RetainDirectoryAncestors(Path.Combine(root, "installer-support"));
                            try
                            {
                                foreach (string relative in new string[] { ".soai-install-root", "soai.exe.config", "installer-support\\Remove-SoAI.ps1", "installer-support\\Shared-SoAIResourceOwnership.ps1", "installer-support\\installed-files.txt", "installer-support\\UninstallWorker.exe" })
                                {
                                    RequireRegularFile(Path.Combine(root, relative));
                                }
                                stage = Path.Combine(Path.GetDirectoryName(root), StageNamePrefix + Guid.NewGuid().ToString("N"));
                                NativeFilesystemHandles.CreateProtectedDirectory(stage, InstallationSecurity.RootSecurity);
                                ancestors.AddRange(NativeFilesystemHandles.RetainDirectoryAncestors(stage));
                                foreach (string name in new string[] { "Remove-SoAI.ps1", "Shared-SoAIResourceOwnership.ps1", "installed-files.txt", "UninstallWorker.exe" })
                                {
                                    File.Copy(Path.Combine(nativeRoot, "installer-support", name), LauncherPaths.ToNativeFilesystemPath(Path.Combine(stage, name)), false);
                                }
                                RequireRegularFile(Path.Combine(root, "soai.exe"));
                                File.Copy(Path.Combine(nativeRoot, "soai.exe"), LauncherPaths.ToNativeFilesystemPath(Path.Combine(stage, "soai-control.exe")), false);
                                File.Copy(Path.Combine(nativeRoot, "soai.exe.config"), LauncherPaths.ToNativeFilesystemPath(Path.Combine(stage, "Uninstall.exe.config")), false);
                                NativeFilesystemHandles.WriteNewDurableFile(Path.Combine(stage, InstallationRootRecord), root);
                                File.Copy(LauncherPaths.ToNativeFilesystemPath(image), LauncherPaths.ToNativeFilesystemPath(Path.Combine(stage, "Uninstall.exe")), false);
                                SetRecoveryRegistration(root, stage);
                            }
                            finally { foreach (SafeFileHandle sourceHandle in sources) { sourceHandle.Dispose(); } }
                        }
                        if (image.StartsWith(root.TrimEnd('\\') + "\\", StringComparison.OrdinalIgnoreCase))
                        {
                            string relocated = Path.Combine(stage, "completion-owner-" + Guid.NewGuid().ToString("N") + ".exe");
                            File.Move(LauncherPaths.ToNativeFilesystemPath(image), LauncherPaths.ToNativeFilesystemPath(relocated));
                            File.Copy(LauncherPaths.ToNativeFilesystemPath(Path.Combine(stage, "Uninstall.exe")), LauncherPaths.ToNativeFilesystemPath(image), false);
                        }
                        Environment.CurrentDirectory = stage;
                        string inheritedTemp = Environment.GetEnvironmentVariable("TEMP");
                        string inheritedTmp = Environment.GetEnvironmentVariable("TMP");
                        Environment.SetEnvironmentVariable("TEMP", stage);
                        Environment.SetEnvironmentVariable("TMP", stage);
                        Environment.SetEnvironmentVariable("SOAI_UNINSTALL_OWNER_PID", Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture));
                        Environment.SetEnvironmentVariable("SOAI_UNINSTALL_OWNER_IMAGE", NativeBackendJob.ReadProcessImagePath(NativeBackendJob.GetCurrentProcess()));
                        string workerFailurePath = Path.Combine(stage, "worker-failure-" + Guid.NewGuid().ToString("N") + ".txt");
                        Environment.SetEnvironmentVariable("SOAI_INSTALLER_FAILURE_PATH", workerFailurePath);
                        Environment.SetEnvironmentVariable("SOAI_UNINSTALL_ROOT", root);
                        Environment.SetEnvironmentVariable("SOAI_UNINSTALL_SUPPORT_ROOT", stage);
                        string selectedPath = LauncherPaths.ToNativeFilesystemPath(Path.Combine(stage, "selected-mode.txt"));
                        if (File.Exists(selectedPath))
                        {
                            string retainedSelection = File.ReadAllText(selectedPath, Encoding.ASCII).Trim();
                            if (retainedSelection != "all" && retainedSelection != "retain") { throw new InvalidOperationException("Uninstall recovery has no valid selected mode."); }
                            if (retainedSelection == "all" && !args.Contains("/REMOVEAPPDATA"))
                            {
                                args = args.Concat(new string[] { "/REMOVEAPPDATA" }).ToArray();
                            }
                            bool requestedAll = args.Contains("/REMOVEAPPDATA");
                            if (requestedAll == (retainedSelection == "all") && HasCompletedFilesystemCleanup(root, requestedAll))
                            {
                                return CompleteSuccessfulUninstall(root, stage, requestedAll, inheritedTemp, inheritedTmp);
                            }
                        }
                        string worker = Path.Combine(stage, "UninstallWorker.exe");
                        RequireRegularFile(worker);
                        string arguments = string.Join(" ", args) + " _?=" + root;
                        int result;
                        using (NativeBackendJob cleanup = NativeBackendJob.StartProcess(worker, arguments, stage, Path.Combine(stage, "cleanup.log"), false))
                        {
                            cleanup.Commit();
                            if (!cleanup.ProcessHandle.WaitForExit(1800000))
                            {
                                throw new TimeoutException("The uninstall worker is still running. Its recovery entrypoint and diagnostics were retained.");
                            }
                            result = cleanup.ExitCode;
                            Stopwatch settlement = Stopwatch.StartNew();
                            while (cleanup.HasActiveProcesses())
                            {
                                if (settlement.Elapsed >= TimeSpan.FromSeconds(30)) { throw new TimeoutException("Uninstall cleanup descendants remain active."); }
                                Thread.Sleep(25);
                            }
                        }
                        if (result != 0)
                        {
                            Console.Error.WriteLine("SoAI uninstall cleanup failed with exit code " + result.ToString(CultureInfo.InvariantCulture) + ". Retry the retained uninstall entrypoint. Diagnostic reference: " + stage);
                            if (File.Exists(LauncherPaths.ToNativeFilesystemPath(workerFailurePath)))
                            {
                                RequireRegularFile(workerFailurePath);
                                Console.Error.WriteLine("The specific uninstall cause is retained in the worker-failure record: " + workerFailurePath);
                            }
                            return result;
                        }
                        string selection = File.ReadAllText(LauncherPaths.ToNativeFilesystemPath(Path.Combine(stage, "selected-mode.txt")), Encoding.ASCII).Trim();
                        if (selection != "retain" && selection != "all") { throw new InvalidOperationException("The uninstall worker did not report its selected cleanup mode."); }
                        return CompleteSuccessfulUninstall(root, stage, selection == "all", inheritedTemp, inheritedTmp);
                    }
                }
            }
            catch (Exception exception)
            {
                string reference = Guid.NewGuid().ToString("N");
                if (stage != null)
                {
                    try { NativeFilesystemHandles.WriteNewDurableFile(Path.Combine(stage, "failure-" + reference + ".txt"), exception.ToString()); }
                    catch (Exception diagnosticFailure) { Console.Error.WriteLine("Uninstall diagnostics could not be saved: " + diagnosticFailure.GetType().Name); }
                }
                else { reference = LauncherDiagnostics.WriteStartupFailure(diagnosticPaths, exception); }
                string cause = exception is InvalidOperationException || exception is ArgumentException || exception is TimeoutException
                    ? exception.Message : exception is UnauthorizedAccessException || (exception is Win32Exception && ((Win32Exception)exception).NativeErrorCode == 5)
                        ? "Windows denied access to required uninstall files or registration." : "Windows could not verify uninstall cleanup.";
                Console.Error.WriteLine("SoAI uninstall did not complete. " + cause + " Retry its retained uninstall entrypoint or repair with SoAI Setup. Diagnostic reference: " + reference + ". Recovery directory: " + stage);
                return 1;
            }
            finally { foreach (SafeFileHandle ancestor in ancestors) { ancestor.Dispose(); } }
        }

        private static void RequireRegularFile(string path)
        {
            using (SafeFileHandle handle = NativeFilesystemHandles.CreateFile(LauncherPaths.ToNativeFilesystemPath(path), 0x80, 1, IntPtr.Zero, 3, 0x00200000, IntPtr.Zero))
            {
                NativeFilesystemHandles.FileHandleInformation information;
                if (handle.IsInvalid || !NativeFilesystemHandles.GetFileInformationByHandle(handle, out information)
                    || (information.Attributes & 0x410) != 0 || information.Links != 1)
                {
                    throw new InvalidOperationException("A required uninstall file is missing or cannot be safely verified. Registration was retained.");
                }
            }
        }

        private static void SetRecoveryRegistration(string root, string stage)
        {
            using (RegistryKey machine = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
            using (RegistryKey registration = machine.OpenSubKey(UninstallKey, true))
            {
                if (registration == null || !string.Equals(registration.GetValue("InstallLocation") as string, root, StringComparison.OrdinalIgnoreCase)) { return; }
                string command = BackendProcess.Quote(Path.Combine(stage, "Uninstall.exe")) + " " + RecoveryArgument + " " + BackendProcess.Quote(root);
                registration.SetValue("UninstallString", command);
                registration.SetValue("QuietUninstallString", command + " /S");
                registration.SetValue("SoAIRecoveryDirectory", stage);
                registration.Flush();
            }
        }

        public static bool HasCompletedFilesystemCleanup(string root, bool removeData)
        {
            string nativeRoot = LauncherPaths.ToNativeFilesystemPath(root);
            uint attributes = NativeFilesystemHandles.GetFileAttributes(nativeRoot);
            if (attributes == uint.MaxValue)
            {
                int failure = Marshal.GetLastWin32Error();
                if (failure == 2 || failure == 3) { return removeData; }
                throw new Win32Exception(failure, "The uninstall root could not be inspected.");
            }
            if ((attributes & 0x410) != 0x10) { throw new InvalidOperationException("The uninstall root is not a verified directory."); }
            foreach (string entry in Directory.GetFileSystemEntries(nativeRoot))
            {
                string name = Path.GetFileName(entry);
                if (string.Equals(name, ".soai-install-root", StringComparison.OrdinalIgnoreCase)) { continue; }
                if (removeData) { return false; }
                if (string.Equals(name, "data", StringComparison.OrdinalIgnoreCase)) { continue; }
                if (!string.Equals(name, "installer-support", StringComparison.OrdinalIgnoreCase) || !Directory.Exists(entry)) { return false; }
                foreach (string supportEntry in Directory.GetFileSystemEntries(entry))
                {
                    string supportName = Path.GetFileName(supportEntry);
                    if (!string.Equals(supportName, "Remove-SoAI.ps1", StringComparison.OrdinalIgnoreCase)
                        && !string.Equals(supportName, "Shared-SoAIResourceOwnership.ps1", StringComparison.OrdinalIgnoreCase)
                        && !string.Equals(supportName, "installed-files.txt", StringComparison.OrdinalIgnoreCase)) { return false; }
                }
            }
            return true;
        }

        private static void VerifyPostconditions(string root, string stage, bool removeData)
        {
            string nativeRoot = LauncherPaths.ToNativeFilesystemPath(root);
            if (!HasCompletedFilesystemCleanup(root, removeData))
            {
                throw new InvalidOperationException("The selected uninstall mode retained application entries.");
            }
            if (!ServiceRegistration.WaitForStopped(root, TimeSpan.Zero)) { throw new InvalidOperationException("The SoAI service is still running."); }
            string verificationPath = Path.Combine(stage, "verified-" + Guid.NewGuid().ToString("N") + ".txt");
            string arguments = PowerShellArguments + " -File " + BackendProcess.Quote(Path.Combine(stage, "Remove-SoAI.ps1"))
                + " -Mode VerifyUninstall -InstallRoot " + BackendProcess.Quote(root)
                + " -ControlLauncherPath " + BackendProcess.Quote(Path.Combine(stage, "soai-control.exe"))
                + " -VerificationPath " + BackendProcess.Quote(verificationPath)
                + (removeData ? " -RemoveApplicationData" : string.Empty);
            using (NativeBackendJob verification = NativeBackendJob.StartProcess(SystemPowerShellPath(), arguments, stage, Path.Combine(stage, "verification.log"), false))
            {
                if (!verification.ProcessHandle.WaitForExit(60000) || verification.ExitCode != 0
                    || !File.Exists(LauncherPaths.ToNativeFilesystemPath(verificationPath))
                    || File.ReadAllText(LauncherPaths.ToNativeFilesystemPath(verificationPath), Encoding.UTF8) != (removeData ? "all" : "retain") + "\n" + root)
                {
                    throw new InvalidOperationException("The selected uninstall mode did not satisfy shared ownership postconditions.");
                }
            }
            if (removeData && Directory.Exists(nativeRoot))
            {
                string marker = Path.Combine(nativeRoot, ".soai-install-root");
                if (File.Exists(marker)) { RequireRegularFile(marker); File.Delete(marker); }
                Directory.Delete(nativeRoot, false);
            }
        }

        private static void RemoveRegistration(string root)
        {
            ServiceRegistration.ClearStopDeadline(root, null);
            using (RegistryKey machine = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
            {
                bool removeProduct;
                using (RegistryKey product = machine.OpenSubKey(ProductKey))
                {
                    removeProduct = product != null && string.Equals(product.GetValue("InstallDir") as string, root, StringComparison.OrdinalIgnoreCase);
                }
                bool removeUninstall;
                using (RegistryKey uninstall = machine.OpenSubKey(UninstallKey))
                {
                    removeUninstall = uninstall != null && string.Equals(uninstall.GetValue("InstallLocation") as string, root, StringComparison.OrdinalIgnoreCase);
                }
                if (removeProduct) { machine.DeleteSubKeyTree(ProductKey, false); }
                if (removeUninstall) { machine.DeleteSubKeyTree(UninstallKey, false); }
                machine.Flush();
            }
        }

        private static string SystemPowerShellPath()
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0", "powershell.exe");
        }

        private static int CompleteSuccessfulUninstall(string root, string stage, bool removeData, string inheritedTemp, string inheritedTmp)
        {
            VerifyPostconditions(root, stage, removeData);
            RecordSuccessfulCompletion(stage);
            RemoveRegistration(root);
            Environment.SetEnvironmentVariable("TEMP", inheritedTemp);
            Environment.SetEnvironmentVariable("TMP", inheritedTmp);
            HandOffStageRemoval(root, stage);
            return 0;
        }

        private static void RecordSuccessfulCompletion(string stage)
        {
            string marker = Path.Combine(stage, SuccessRecord);
            if (NativeFilesystemHandles.GetFileAttributes(LauncherPaths.ToNativeFilesystemPath(marker)) == uint.MaxValue)
            {
                int failure = Marshal.GetLastWin32Error();
                if (failure != 2) { throw new Win32Exception(failure, "The uninstall completion record could not be inspected."); }
                NativeFilesystemHandles.WriteNewDurableFile(marker, SuccessRecordText);
            }
            RequireSuccessRecord(stage);
        }

        private static void RequireSuccessRecord(string stage)
        {
            string marker = Path.Combine(stage, SuccessRecord);
            RequireRegularFile(marker);
            if (!File.ReadAllBytes(LauncherPaths.ToNativeFilesystemPath(marker)).SequenceEqual(new UTF8Encoding(false).GetBytes(SuccessRecordText)))
            {
                throw new InvalidOperationException("The uninstall completion record is not valid. It was retained for inspection.");
            }
        }

        private static string RequireCompletionEvidence(string stage)
        {
            RequireSuccessRecord(stage);
            string record = Path.Combine(stage, InstallationRootRecord);
            RequireRegularFile(record);
            string root = File.ReadAllText(LauncherPaths.ToNativeFilesystemPath(record), Encoding.UTF8);
            if (!LauncherPaths.IsAbsoluteFilesystemPath(root) || !string.Equals(Path.GetFullPath(root), root, StringComparison.Ordinal)
                || string.Equals(root, stage, StringComparison.OrdinalIgnoreCase)
                || !string.Equals(Path.GetDirectoryName(root), Path.GetDirectoryName(stage), StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("The uninstall installation record does not identify a sibling installation folder.");
            }
            return root;
        }

        private static void HandOffStageRemoval(string root, string stage)
        {
            string reference = Guid.NewGuid().ToString("N");
            NativeFilesystemHandles.FileHandleInformation? identity = null;
            NativeBackendJob finalizer = null;
            bool committed = false;
            Exception failure = null;
            try
            {
                identity = ReadEntryIdentity(stage, true);
                string temporary;
                List<SafeFileHandle> logAncestors;
                try
                {
                    temporary = LauncherPaths.FromRoot(Path.GetTempPath()).RootDirectory;
                    logAncestors = NativeFilesystemHandles.RetainDirectoryAncestors(temporary);
                }
                catch (Exception unavailable)
                {
                    if (!(unavailable is Win32Exception) && !(unavailable is InvalidOperationException) && !(unavailable is IOException)) { throw; }
                    throw new InvalidOperationException("The Windows temporary folder is unavailable for the staging folder finalizer log.", unavailable);
                }
                try
                {
                    if (IsSameOrInside(temporary, stage) || IsSameOrInside(temporary, root))
                    {
                        throw new InvalidOperationException("The Windows temporary folder is inside the uninstall staging or installation folder.");
                    }
                    string control = Path.Combine(stage, "soai-control.exe");
                    RequireRegularFile(control);
                    if (!string.Equals(RequireCompletionEvidence(stage), root, StringComparison.OrdinalIgnoreCase))
                    {
                        throw new InvalidOperationException("The uninstall completion evidence identifies another installation.");
                    }
                    string logPath = Path.Combine(temporary, StageRemovalLogPrefix + reference + ".log");
                    int ownerProcessId;
                    long ownerStartTicks;
                    using (Process current = Process.GetCurrentProcess())
                    {
                        ownerProcessId = current.Id;
                        ownerStartTicks = current.StartTime.ToUniversalTime().Ticks;
                    }
                    string command = "$ErrorActionPreference = 'Stop'\n"
                        + "[AppContext]::SetSwitch('Switch.System.IO.UseLegacyPathHandling', $false)\n"
                        + "[AppContext]::SetSwitch('Switch.System.IO.BlockLongPaths', $false)\n"
                        + "[Reflection.Assembly]::Load([IO.File]::ReadAllBytes(" + PowerShellText(LauncherPaths.ToNativeFilesystemPath(control)) + ")) | Out-Null\n"
                        + "exit ([SoAILauncher.SynchronousUninstall]::RemoveCompletedStage(" + PowerShellText(stage) + ", " + PowerShellText(reference) + ", "
                        + ownerProcessId.ToString(CultureInfo.InvariantCulture) + ", " + ownerStartTicks.ToString(CultureInfo.InvariantCulture) + ", " + PowerShellText(logPath) + "))\n";
                    finalizer = NativeBackendJob.StartProcess(SystemPowerShellPath(), PowerShellArguments + " -EncodedCommand " + Convert.ToBase64String(Encoding.Unicode.GetBytes(command)),
                        Environment.GetFolderPath(Environment.SpecialFolder.System), logPath, false);
                }
                finally { foreach (SafeFileHandle ancestor in logAncestors) { ancestor.Dispose(); } }
                AwaitStageRemovalAcknowledgement(finalizer, Path.Combine(stage, StageRemovalReadyPrefix + reference + ".txt"));
                finalizer.Commit();
                committed = true;
            }
            catch (Exception handoffFailure) { failure = handoffFailure; }
            bool ownershipVerified = true;
            if (finalizer != null)
            {
                try { finalizer.Dispose(); }
                catch (Exception disposalFailure)
                {
                    ownershipVerified = committed;
                    failure = failure == null ? disposalFailure : new AggregateException(failure, disposalFailure);
                }
            }
            if (failure == null) { return; }
            try
            {
                if (committed)
                {
                    Console.Error.WriteLine("The SoAI uninstall staging folder removal continues in its finalizer. Its handoff cleanup reported: " + failure.Message);
                    return;
                }
                if (!ownershipVerified)
                {
                    failure = new InvalidOperationException("The uninstall staging folder finalizer could not be confirmed stopped, so cleanup ownership is uncertain.", failure);
                }
                ReportStageRemovalFailure(stage, identity, reference, failure, 0, ownershipVerified, Console.Error);
            }
            catch (Exception reportingFailure)
            {
                try { Console.Error.WriteLine("SoAI uninstall completed, but its staging folder cleanup could not be reported: " + reportingFailure.Message + " Staging folder: " + stage); }
                catch (IOException) { }
            }
        }

        private static string PowerShellText(string value)
        {
            return "([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + Convert.ToBase64String(new UTF8Encoding(false).GetBytes(value)) + "')))";
        }

        private static void AwaitStageRemovalAcknowledgement(NativeBackendJob finalizer, string readyPath)
        {
            string expected = finalizer.ProcessHandle.Id.ToString(CultureInfo.InvariantCulture);
            Stopwatch deadline = Stopwatch.StartNew();
            while (true)
            {
                string acknowledgement = ReadAcknowledgement(readyPath);
                if (acknowledgement != null)
                {
                    if (!string.Equals(acknowledgement, expected, StringComparison.Ordinal))
                    {
                        throw new InvalidOperationException("The uninstall staging folder removal acknowledgement does not identify its finalizer.");
                    }
                    if (finalizer.HasExited)
                    {
                        throw new InvalidOperationException("The uninstall staging folder finalizer exited after acknowledging its handoff.");
                    }
                    return;
                }
                if (finalizer.HasExited)
                {
                    throw new InvalidOperationException("The uninstall staging folder finalizer exited with code " + finalizer.ExitCode.ToString(CultureInfo.InvariantCulture) + " before acknowledging its handoff.");
                }
                if (deadline.ElapsedMilliseconds >= StageRemovalWaitMilliseconds)
                {
                    throw new TimeoutException("The uninstall staging folder finalizer did not acknowledge its handoff within 60 seconds.");
                }
                Thread.Sleep(50);
            }
        }

        private static string ReadAcknowledgement(string path)
        {
            byte[] content;
            try
            {
                using (FileStream stream = new FileStream(LauncherPaths.ToNativeFilesystemPath(path), FileMode.Open, FileAccess.Read, FileShare.Read))
                {
                    if (stream.Length > 32) { throw new InvalidOperationException("The uninstall staging folder removal acknowledgement is malformed."); }
                    content = new byte[stream.Length];
                    int offset = 0;
                    while (offset < content.Length)
                    {
                        int read = stream.Read(content, offset, content.Length - offset);
                        if (read == 0) { throw new InvalidOperationException("The uninstall staging folder removal acknowledgement changed while it was read."); }
                        offset += read;
                    }
                }
            }
            catch (FileNotFoundException) { return null; }
            catch (IOException exception)
            {
                if ((exception.HResult & 0xFFFF) == 32) { return null; }
                throw;
            }
            RequireRegularFile(path);
            return new UTF8Encoding(false, true).GetString(content);
        }

        public static int RemoveCompletedStage(string stage, string reference, int ownerProcessId, long ownerStartTicks, string logPath)
        {
            List<SafeFileHandle> ancestors = new List<SafeFileHandle>();
            Process owner = null;
            try
            {
                NativeFilesystemHandles.FileHandleInformation stageIdentity;
                NativeFilesystemHandles.FileHandleInformation logIdentity;
                string root;
                try
                {
                    if (ownerProcessId <= 0 || ownerStartTicks <= 0 || reference == null || !Regex.IsMatch(reference, "\\A[0-9a-f]{32}\\z", RegexOptions.CultureInvariant)
                        || !IsCanonicalPath(stage) || !Regex.IsMatch(Path.GetFileName(stage), "\\A" + Regex.Escape(StageNamePrefix) + "[0-9a-f]{32}\\z", RegexOptions.CultureInvariant)
                        || !IsCanonicalPath(logPath) || !string.Equals(Path.GetFileName(logPath), StageRemovalLogPrefix + reference + ".log", StringComparison.Ordinal))
                    {
                        throw new ArgumentException("The uninstall staging folder removal handoff is invalid.");
                    }
                    string logDirectory = Path.GetDirectoryName(logPath);
                    ancestors.AddRange(NativeFilesystemHandles.RetainDirectoryAncestors(Path.GetDirectoryName(stage)));
                    ancestors.AddRange(NativeFilesystemHandles.RetainDirectoryAncestors(logDirectory));
                    stageIdentity = ReadEntryIdentity(stage, true);
                    root = RequireCompletionEvidence(stage);
                    if (IsSameOrInside(logDirectory, stage) || IsSameOrInside(logDirectory, root))
                    {
                        throw new ArgumentException("The uninstall staging folder removal log is not outside the staging and installation folders.");
                    }
                    logIdentity = ReadEntryIdentity(logPath, false);
                    if (RegistrationReferencesStage(stage))
                    {
                        throw new InvalidOperationException("Windows uninstall registration still references this staging folder.");
                    }
                    InspectStage(stage, stageIdentity);
                    owner = OpenVerifiedOwner(ownerProcessId, ownerStartTicks);
                    using (Process current = Process.GetCurrentProcess())
                    {
                        NativeFilesystemHandles.WriteNewDurableFile(Path.Combine(stage, StageRemovalReadyPrefix + reference + ".txt"), current.Id.ToString(CultureInfo.InvariantCulture));
                    }
                }
                catch (Exception rejection)
                {
                    Console.Out.WriteLine("SoAI rejected the uninstall staging folder removal handoff and changed nothing: " + rejection);
                    return 2;
                }
                int removed = 0;
                try
                {
                    if (owner != null && !owner.WaitForExit(StageRemovalWaitMilliseconds))
                    {
                        throw new TimeoutException("The uninstall completion owner did not exit within 60 seconds.");
                    }
                    if (!IsRetainedStage(stage, stageIdentity) || !string.Equals(RequireCompletionEvidence(stage), root, StringComparison.OrdinalIgnoreCase) || RegistrationReferencesStage(stage))
                    {
                        throw new InvalidOperationException("The uninstall staging folder or its completion evidence changed after the handoff.");
                    }
                    RemoveStageTree(stage, stageIdentity, ref removed);
                }
                catch (Exception failure)
                {
                    ReportStageRemovalFailure(stage, stageIdentity, reference, failure, removed, !(failure is InvalidOperationException), Console.Out);
                    return 1;
                }
                try
                {
                    using (StageEntry log = OpenStageEntry(logPath, true))
                    {
                        if (!IsSameEntry(log.Information, logIdentity)) { throw new InvalidOperationException("The removal log was replaced."); }
                        NativeFilesystemHandles.SetDeleteDisposition(log.Handle, "The removal log could not be removed.");
                    }
                }
                catch (Exception logFailure)
                {
                    Console.Out.WriteLine("SoAI removed the uninstall staging folder " + stage + ", but this removal log was retained: " + logFailure.Message);
                    return 3;
                }
                return 0;
            }
            finally
            {
                if (owner != null) { owner.Dispose(); }
                foreach (SafeFileHandle ancestor in ancestors) { ancestor.Dispose(); }
            }
        }

        private static bool IsCanonicalPath(string path)
        {
            if (string.IsNullOrEmpty(path) || !LauncherPaths.IsAbsoluteFilesystemPath(path)
                || !string.Equals(LauncherPaths.RemoveWindowsPathNamespace(path), path, StringComparison.Ordinal)
                || !string.Equals(Path.GetFullPath(path), path, StringComparison.Ordinal))
            {
                return false;
            }
            string parent = Path.GetDirectoryName(path);
            return !string.IsNullOrEmpty(parent) && !string.IsNullOrEmpty(Path.GetFileName(path))
                && string.Equals(LauncherPaths.FromRoot(parent).RootDirectory, parent, StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsSameOrInside(string path, string container)
        {
            return string.Equals(path, container, StringComparison.OrdinalIgnoreCase)
                || path.StartsWith(container.TrimEnd('\\') + "\\", StringComparison.OrdinalIgnoreCase);
        }

        private static bool RegistrationReferencesStage(string stage)
        {
            using (RegistryKey machine = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
            using (RegistryKey registration = machine.OpenSubKey(UninstallKey))
            {
                if (registration == null) { return false; }
                foreach (string name in new string[] { "SoAIRecoveryDirectory", "UninstallString", "QuietUninstallString" })
                {
                    string value = registration.GetValue(name) as string;
                    if (value != null && value.IndexOf(stage, StringComparison.OrdinalIgnoreCase) >= 0) { return true; }
                }
                return false;
            }
        }

        private static Process OpenVerifiedOwner(int ownerProcessId, long ownerStartTicks)
        {
            Process owner;
            try { owner = Process.GetProcessById(ownerProcessId); }
            catch (ArgumentException) { return null; }
            try
            {
                IntPtr ownerHandle = owner.Handle;
                if (ownerHandle == IntPtr.Zero)
                {
                    throw new InvalidOperationException("The uninstall completion owner cannot be verified.");
                }
                if (owner.HasExited || owner.StartTime.ToUniversalTime().Ticks != ownerStartTicks)
                {
                    owner.Dispose();
                    return null;
                }
                return owner;
            }
            catch
            {
                owner.Dispose();
                throw;
            }
        }

        private sealed class StageEntry : IDisposable
        {
            public readonly string Path;
            public readonly SafeFileHandle Handle;
            public readonly NativeFilesystemHandles.FileHandleInformation Information;
            public readonly List<StageEntry> Children = new List<StageEntry>();

            public StageEntry(string path, SafeFileHandle handle, NativeFilesystemHandles.FileHandleInformation information)
            {
                Path = path;
                Handle = handle;
                Information = information;
            }

            public bool IsDirectory { get { return (Information.Attributes & 0x10) != 0; } }

            public void Dispose()
            {
                foreach (StageEntry child in Children) { child.Dispose(); }
                Handle.Dispose();
            }
        }

        private static StageEntry OpenStageEntry(string path, bool deletion)
        {
            string nativePath = LauncherPaths.ToNativeFilesystemPath(path);
            SafeFileHandle handle = NativeFilesystemHandles.CreateFile(nativePath, deletion ? 0x10180u : 0x80u, deletion ? 3u : 7u, IntPtr.Zero, 3, 0x02200000, IntPtr.Zero);
            NativeFilesystemHandles.FileHandleInformation information;
            uint pathAttributes = uint.MaxValue;
            if (handle.IsInvalid || !NativeFilesystemHandles.GetFileInformationByHandle(handle, out information)
                || (pathAttributes = NativeFilesystemHandles.GetFileAttributes(nativePath)) == uint.MaxValue)
            {
                int failure = Marshal.GetLastWin32Error();
                handle.Dispose();
                throw new Win32Exception(failure, "An uninstall staging entry could not be opened: " + path);
            }
            if (((information.Attributes | pathAttributes) & 0x400) != 0 || ((information.Attributes & 0x10) == 0 && information.Links != 1))
            {
                handle.Dispose();
                throw new InvalidOperationException("An uninstall staging entry is a link and was retained for inspection: " + path);
            }
            return new StageEntry(path, handle, information);
        }

        private static NativeFilesystemHandles.FileHandleInformation ReadEntryIdentity(string path, bool directory)
        {
            using (StageEntry entry = OpenStageEntry(path, false))
            {
                if (entry.IsDirectory != directory)
                {
                    throw new InvalidOperationException("An uninstall staging entry has an unexpected type: " + path);
                }
                return entry.Information;
            }
        }

        private static bool IsSameEntry(NativeFilesystemHandles.FileHandleInformation current, NativeFilesystemHandles.FileHandleInformation retained)
        {
            return current.VolumeSerial == retained.VolumeSerial && current.IndexHigh == retained.IndexHigh && current.IndexLow == retained.IndexLow;
        }

        private static bool IsRetainedStage(string stage, NativeFilesystemHandles.FileHandleInformation identity)
        {
            try { return IsSameEntry(ReadEntryIdentity(stage, true), identity); }
            catch (Win32Exception) { return false; }
            catch (InvalidOperationException) { return false; }
        }

        private static StageEntry OpenStageTree(string stage, NativeFilesystemHandles.FileHandleInformation identity, bool deletion)
        {
            StageEntry root = OpenStageEntry(stage, deletion);
            try
            {
                if (!root.IsDirectory || !IsSameEntry(root.Information, identity))
                {
                    throw new InvalidOperationException("The uninstall staging folder was replaced and was retained for inspection.");
                }
                Stack<StageEntry> pending = new Stack<StageEntry>();
                pending.Push(root);
                while (pending.Count > 0)
                {
                    StageEntry directory = pending.Pop();
                    foreach (string child in Directory.EnumerateFileSystemEntries(LauncherPaths.ToNativeFilesystemPath(directory.Path)))
                    {
                        StageEntry entry = OpenStageEntry(Path.Combine(directory.Path, Path.GetFileName(child)), deletion);
                        directory.Children.Add(entry);
                        if (entry.IsDirectory) { pending.Push(entry); }
                    }
                }
                return root;
            }
            catch
            {
                root.Dispose();
                throw;
            }
        }

        private static List<string> InspectStage(string stage, NativeFilesystemHandles.FileHandleInformation identity)
        {
            List<string> entries = new List<string>();
            using (StageEntry root = OpenStageTree(stage, identity, false))
            {
                AddChildrenFirst(root, entries);
            }
            return entries;
        }

        private static void AddChildrenFirst(StageEntry entry, List<string> entries)
        {
            foreach (StageEntry child in entry.Children) { AddChildrenFirst(child, entries); }
            entries.Add(entry.Path);
        }

        private static void RemoveStageTree(string stage, NativeFilesystemHandles.FileHandleInformation identity, ref int removed)
        {
            Stopwatch budget = Stopwatch.StartNew();
            int delay = 50;
            while (true)
            {
                try
                {
                    using (StageEntry root = OpenStageTree(stage, identity, true))
                    {
                        DeleteChildrenFirst(root, ref removed);
                    }
                    return;
                }
                catch (Exception failure)
                {
                    Win32Exception nativeFailure = failure as Win32Exception;
                    bool retryable = nativeFailure != null
                        ? Array.IndexOf(new int[] { 2, 3, 5, 32, 33, 145 }, nativeFailure.NativeErrorCode) >= 0
                        : failure is IOException || failure is UnauthorizedAccessException;
                    if (!retryable || budget.ElapsedMilliseconds + delay > StageRemovalWaitMilliseconds) { throw; }
                    Console.Out.WriteLine("Retrying the uninstall staging folder removal after: " + failure.Message);
                }
                Thread.Sleep(delay);
                delay = Math.Min(delay * 2, 2000);
            }
        }

        private static void DeleteChildrenFirst(StageEntry entry, ref int removed)
        {
            foreach (StageEntry child in entry.Children) { DeleteChildrenFirst(child, ref removed); }
            if ((entry.Information.Attributes & 0x1) != 0)
            {
                NativeFilesystemHandles.ClearReadOnlyAttribute(entry.Handle, entry.Information.Attributes, "An uninstall staging entry could not be made writable: " + entry.Path);
            }
            NativeFilesystemHandles.SetDeleteDisposition(entry.Handle, "An uninstall staging entry could not be removed: " + entry.Path);
            entry.Handle.Dispose();
            removed++;
        }

        private static void ReportStageRemovalFailure(string stage, NativeFilesystemHandles.FileHandleInformation? identity, string reference, Exception cause, int removed, bool scheduleRestart, TextWriter output)
        {
            output.WriteLine("SoAI uninstall completed, but its staging folder " + stage + " could not be removed immediately (reference " + reference + ", "
                + removed.ToString(CultureInfo.InvariantCulture) + " entries removed before the failure): " + cause);
            bool retained = identity.HasValue && IsRetainedStage(stage, identity.Value);
            if (retained)
            {
                try
                {
                    NativeFilesystemHandles.WriteNewDurableFile(Path.Combine(stage, StageRemovalFailurePrefix + reference + ".txt"),
                        "Staging folder: " + stage + "\r\nReference: " + reference + "\r\nEntries removed before the failure: " + removed.ToString(CultureInfo.InvariantCulture) + "\r\n" + cause);
                }
                catch (Exception recordFailure) { output.WriteLine("The staging folder failure record could not be saved: " + recordFailure.Message); }
            }
            if (!retained)
            {
                output.WriteLine("The staging folder could not be verified, so nothing was written to it or scheduled for removal.");
                return;
            }
            if (!scheduleRestart)
            {
                output.WriteLine("The staging folder was retained for inspection and was not scheduled for removal.");
                return;
            }
            List<string> entries;
            try { entries = InspectStage(stage, identity.Value); }
            catch (Exception revalidationFailure)
            {
                output.WriteLine("The staging folder could not be revalidated and was not scheduled for removal: " + revalidationFailure.Message);
                return;
            }
            int accepted = 0;
            foreach (string entry in entries)
            {
                try
                {
                    NativeFilesystemHandles.ScheduleRemovalAtRestart(entry);
                    accepted++;
                    output.WriteLine("Removal was scheduled for the next Windows restart: " + entry);
                }
                catch (Win32Exception schedulingFailure) { output.WriteLine("Windows did not accept restart removal of " + entry + ": " + schedulingFailure.Message); }
            }
            output.WriteLine(accepted == entries.Count
                ? "Removal of the staging folder was scheduled for the next Windows restart."
                : "Removal was scheduled for only " + accepted.ToString(CultureInfo.InvariantCulture) + " of " + entries.Count.ToString(CultureInfo.InvariantCulture)
                    + " staging entries; the remaining entries stay in " + stage + ".");
        }
    }

    internal sealed class PublicStopDeadline
    {
        private const string HandoffArgument = "--soai-stop-deadline";
        private const int FailureOutputReserveMilliseconds = 250;
        private readonly double expires;
        private readonly int waitingParent;

        internal PublicStopDeadline(double expires, int waitingParent)
        {
            this.expires = expires;
            this.waitingParent = waitingParent;
        }

        private static double Now { get { return (double)Stopwatch.GetTimestamp() / Stopwatch.Frequency; } }
        private double ActionDeadline { get { return expires - (double)FailureOutputReserveMilliseconds / 1000; } }
        internal int RemainingMilliseconds { get { return (int)Math.Max(0, Math.Min(int.MaxValue, (ActionDeadline - Now) * 1000)); } }
        internal TimeSpan Remaining { get { return TimeSpan.FromMilliseconds(RemainingMilliseconds); } }

        internal static PublicStopDeadline FromCommand(ref string[] args)
        {
            bool elevated = LauncherCommand.IsElevatedConsoleHandoff(args);
            string[] command = elevated ? LauncherCommand.RemoveElevatedConsoleHandoff(args) : args;
            if (!LauncherCommand.IsStopCommand(command)) { return null; }
            double expires = Now + 150;
            int parent = 0;
            if (command.Length > 1 && command[1] == HandoffArgument && (!elevated || command.Length != 4))
            {
                throw new ArgumentException("The Windows stop completion handoff is invalid.");
            }
            if (elevated && command.Length == 4 && command[1] == HandoffArgument)
            {
                double inherited;
                if (!double.TryParse(command[2], NumberStyles.Float, CultureInfo.InvariantCulture, out inherited)
                    || double.IsNaN(inherited) || double.IsInfinity(inherited)
                    || !int.TryParse(command[3], NumberStyles.None, CultureInfo.InvariantCulture, out parent) || parent <= 0)
                {
                    throw new ArgumentException("The Windows stop completion handoff is invalid.");
                }
                expires = Math.Min(expires, inherited);
                args = new string[] { args[0], command[0] };
            }
            return new PublicStopDeadline(expires, parent);
        }

        internal string ElevationArguments(string[] args)
        {
            return LauncherCommand.BuildElevatedConsoleHandoffArguments(args)
                + " " + HandoffArgument + " " + expires.ToString("R", CultureInfo.InvariantCulture)
                + " " + Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture);
        }

        internal void WriteFailure(string message)
        {
            Task output = Task.Run(delegate { Console.Error.WriteLine(message); });
            output.ContinueWith(delegate(Task completed) { AggregateException observed = completed.Exception; },
                CancellationToken.None, TaskContinuationOptions.OnlyOnFaulted, TaskScheduler.Default);
            Task.WaitAny(new Task[] { output }, (int)Math.Max(0, Math.Min(int.MaxValue, (expires - Now) * 1000)));
        }

        internal int Stop(LauncherPaths paths, string[] args)
        {
            string phase = "verifying launcher ownership";
            List<Process> launchers = new List<Process>();
            Process waitingOwner = null;
            Mutex ownership = null;
            try
            {
                bool created;
                ownership = new Mutex(false, "Global\\SoAI.PublicStop." + LauncherPaths.StableRootIdentity(paths.RootDirectory), out created);
                if (!created) { throw new InvalidOperationException("Another public SoAI stop operation is active for this installation. Wait for its result before retrying."); }
                string launcherPath = Path.Combine(paths.RootDirectory, "soai.exe");
                int current = Process.GetCurrentProcess().Id;
                if (waitingParent != 0)
                {
                    waitingOwner = Process.GetProcessById(waitingParent);
                    if (waitingOwner.HasExited
                        || !string.Equals(NativeBackendJob.ReadProcessImagePath(waitingOwner.Handle), launcherPath, StringComparison.OrdinalIgnoreCase)
                        || waitingOwner.StartTime.ToUniversalTime() > Process.GetCurrentProcess().StartTime.ToUniversalTime())
                    {
                        throw new InvalidOperationException("The public stop owner could not be verified. Retry stop from the installed launcher.");
                    }
                }
                foreach (Process process in Process.GetProcessesByName("soai"))
                {
                    bool retained = false;
                    try
                    {
                        if (process.Id == current || process.Id == waitingParent || process.HasExited) { continue; }
                        if (string.Equals(NativeBackendJob.ReadProcessImagePath(process.Handle), launcherPath, StringComparison.OrdinalIgnoreCase))
                        {
                            launchers.Add(process);
                            retained = true;
                        }
                    }
                    finally { if (!retained) { process.Dispose(); } }
                }
                if (RemainingMilliseconds == 0) { throw new TimeoutException(); }
                phase = "publishing the SoAI service completion deadline";
                ServiceRegistration.PublishStopDeadline(paths, ActionDeadline);
                phase = "waiting for the backend stop control and its output";
                BackendProcess.ConfigureBackendEnvironment(paths);
                Environment.SetEnvironmentVariable("SOAI_WINDOWS_STOP_DEADLINE_SECONDS", ActionDeadline.ToString("R", CultureInfo.InvariantCulture));
                string python = NativeBackendJob.ResolveProcessPath(paths.ResolveStopPythonExecutable(), preserveExecutableNamespace: true);
                BackendProcess.RequireBackendMain(paths);
                using (NativeBackendJob control = NativeBackendJob.StartConsoleProcess(python,
                    BackendProcess.Quote(paths.BackendMain) + BackendProcess.BuildArgumentString(args), paths.RootDirectory))
                {
                    try
                    {
                        if (!control.ProcessHandle.WaitForExit(RemainingMilliseconds)) { throw new TimeoutException(); }
                        int result = control.ExitCode;
                        while (control.HasActiveProcesses())
                        {
                            if (RemainingMilliseconds == 0) { throw new TimeoutException(); }
                            Thread.Sleep(Math.Min(25, RemainingMilliseconds));
                        }
                        if (result != 0) { throw new InvalidOperationException("Backend termination was not verified."); }
                    }
                    finally { control.CancelControl(); }
                }
                phase = "waiting for the SoAI service to settle";
                Task<bool> settlement = Task.Run(delegate { return ServiceRegistration.Stop(paths.RootDirectory, Remaining); });
                if (!settlement.Wait(RemainingMilliseconds))
                {
                    settlement.ContinueWith(delegate(Task<bool> completed) { AggregateException observed = completed.Exception; },
                        CancellationToken.None, TaskContinuationOptions.OnlyOnFaulted, TaskScheduler.Default);
                    throw new TimeoutException();
                }
                if (!settlement.GetAwaiter().GetResult()) { throw new TimeoutException(); }
                ServiceRegistration.RequireSuccessfulStop(paths.RootDirectory);
                phase = "waiting for SoAI launcher acknowledgement";
                foreach (Process launcher in launchers)
                {
                    if (!launcher.HasExited
                        && !DesktopLauncherInstance.TryRequestStop(paths.RootDirectory, launcher)
                        && !launcher.WaitForExit(RemainingMilliseconds))
                    {
                        throw new InvalidOperationException("A SoAI command is still running. Let it finish, then retry stop.");
                    }
                }
                foreach (Process launcher in launchers)
                {
                    if (!launcher.WaitForExit(RemainingMilliseconds)) { throw new TimeoutException(); }
                }
                phase = "verifying that no SoAI launcher or service process remains";
                foreach (Process process in Process.GetProcessesByName("soai"))
                {
                    using (process)
                    {
                        if (process.Id == current || process.Id == waitingParent || process.HasExited) { continue; }
                        if (string.Equals(NativeBackendJob.ReadProcessImagePath(process.Handle), launcherPath, StringComparison.OrdinalIgnoreCase))
                        {
                            throw new InvalidOperationException("A SoAI launcher or service process remains. Close its window and retry stop.");
                        }
                    }
                }
                if (RemainingMilliseconds == 0) { throw new TimeoutException(); }
                ServiceRegistration.ClearStopDeadline(paths.RootDirectory, ActionDeadline);
                return 0;
            }
            catch (Exception exception)
            {
                string cause = exception is TimeoutException ? "The remaining public stop completion budget expired."
                    : exception is UnauthorizedAccessException || (exception is Win32Exception && ((Win32Exception)exception).NativeErrorCode == 5)
                        ? "Windows denied access to the required process or service."
                        : exception is InvalidOperationException ? exception.Message : "Windows could not verify shutdown.";
                string reference = LauncherDiagnostics.WriteStartupFailure(paths,
                    new InvalidOperationException("Stop failed while " + phase + ". " + cause, exception));
                WriteFailure("SoAI stop did not complete while " + phase + ". " + cause
                    + " Recovery evidence was retained. Inspect the SoAI logs and retry stop. Diagnostic reference: " + reference);
                return 1;
            }
            finally
            {
                Environment.SetEnvironmentVariable("SOAI_WINDOWS_STOP_DEADLINE_SECONDS", null);
                foreach (Process launcher in launchers) { launcher.Dispose(); }
                if (waitingOwner != null) { waitingOwner.Dispose(); }
                if (ownership != null) { ownership.Dispose(); }
            }
        }
    }

    internal static class UpdateRecovery
    {
        private const string TransactionPrefix = ".soai_update_transaction_";
        private const string RestorationArgument = "--soai-restore-update";
        private static readonly int RecoveryProcessTimeoutMilliseconds = (int)TimeSpan.FromMinutes(30).TotalMilliseconds;
        private static readonly TimeSpan RestorationHandoffTimeout = TimeSpan.FromMinutes(2);

        private static void CompleteTerminalRecovery(LauncherPaths paths)
        {
            string cleanupPython = paths.ResolveBootstrapPythonExecutable();
            string cleanupBackend = Path.Combine(paths.RootDirectory, "backend");
            string cleanupCode = @"import sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
from app.updater.software_update.install_transaction_recovery import recover_interrupted_update_transactions
from core.logging.trace import get_logger
recovered = recover_interrupted_update_transactions(
    sys.argv[1], get_logger('SoAI.app.updater.windows_startup_cleanup'),
    allow_pending_activation=True, allow_restoration=False,
)
raise SystemExit(0 if recovered else 1)
";
            string cleanupLog = Path.Combine(paths.RootDirectory, "data", "logs", "soai-recovery-cleanup-" + Guid.NewGuid().ToString("N") + ".log");
            string previousPythonPath = Environment.GetEnvironmentVariable("PYTHONPATH");
            string previousBytecode = Environment.GetEnvironmentVariable("PYTHONDONTWRITEBYTECODE");
            try
            {
                Environment.SetEnvironmentVariable("PYTHONPATH", cleanupBackend);
                Environment.SetEnvironmentVariable("PYTHONDONTWRITEBYTECODE", "1");
                using (NativeBackendJob cleanup = NativeBackendJob.StartProcess(
                    cleanupPython, "-P -S -c " + BackendProcess.Quote(cleanupCode) + " " + BackendProcess.Quote(paths.RootDirectory), paths.RootDirectory, cleanupLog))
                {
                    if (!cleanup.ProcessHandle.WaitForExit(RecoveryProcessTimeoutMilliseconds))
                    {
                        throw new TimeoutException("Update transaction cleanup did not finish; preserve the recovery evidence.");
                    }
                    if (cleanup.ProcessHandle.ExitCode != 0)
                    {
                        throw new InvalidOperationException("Shared update cleanup rejected startup. See the recovery cleanup log.");
                    }
                }
            }
            finally
            {
                Environment.SetEnvironmentVariable("PYTHONPATH", previousPythonPath);
                Environment.SetEnvironmentVariable("PYTHONDONTWRITEBYTECODE", previousBytecode);
            }
        }

        public static string InspectRequiredRestoration(LauncherPaths paths)
        {
            RecoverAbandonedInstallationOwnership(paths);
            string[] transactions = Directory.GetFileSystemEntries(paths.RootDirectory, TransactionPrefix + "*");
            if (transactions.Length == 0
                && Directory.GetFileSystemEntries(paths.RootDirectory, ".soai_update_cleanup_*").Length == 0)
            {
                return null;
            }
            string recoveryPython = Path.Combine(paths.StandalonePythonDirectory, "python.exe");
            string recoveryBackend = Path.Combine(paths.RootDirectory, "backend");
            foreach (string transaction in transactions)
            {
                if ((File.GetAttributes(transaction) & FileAttributes.ReparsePoint) != 0 || !Directory.Exists(transaction))
                {
                    throw new InvalidOperationException("Update transaction storage is invalid; preserve it for repair.");
                }
                string retainedPython = Path.Combine(transaction, "recovery_runtime", "python.exe");
                string retainedBackend = Path.Combine(transaction, "old", "backend");
                if (File.Exists(retainedPython) && Directory.Exists(retainedBackend))
                {
                    recoveryPython = retainedPython;
                    recoveryBackend = retainedBackend;
                    break;
                }
            }
            if (!File.Exists(recoveryPython) || !Directory.Exists(recoveryBackend))
            {
                throw new InvalidOperationException("Update recovery bootstrap is missing; preserve the installation for repair.");
            }
            string query = @"import json, sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
from app.updater.software_update.install_transaction_recovery_plan import inspect_update_restorations
print(json.dumps(inspect_update_restorations(sys.argv[1])))
";
            string queryLog = Path.Combine(paths.RootDirectory, "data", "logs", "soai-recovery-inspection-" + Guid.NewGuid().ToString("N") + ".log");
            string previousPythonPath = Environment.GetEnvironmentVariable("PYTHONPATH");
            string previousBytecode = Environment.GetEnvironmentVariable("PYTHONDONTWRITEBYTECODE");
            try
            {
                Environment.SetEnvironmentVariable("PYTHONPATH", recoveryBackend);
                Environment.SetEnvironmentVariable("PYTHONDONTWRITEBYTECODE", "1");
                using (NativeBackendJob inspection = NativeBackendJob.StartProcess(
                    recoveryPython, "-P -S -c " + BackendProcess.Quote(query) + " " + BackendProcess.Quote(paths.RootDirectory), paths.RootDirectory, queryLog))
                {
                    if (!inspection.ProcessHandle.WaitForExit(RecoveryProcessTimeoutMilliseconds))
                    {
                        throw new TimeoutException("Update recovery inspection did not finish.");
                    }
                    if (inspection.ProcessHandle.ExitCode != 0)
                    {
                        throw new InvalidOperationException("Shared update recovery inspection rejected startup. See the recovery inspection log.");
                    }
                }
            }
            finally
            {
                Environment.SetEnvironmentVariable("PYTHONPATH", previousPythonPath);
                Environment.SetEnvironmentVariable("PYTHONDONTWRITEBYTECODE", previousBytecode);
            }
            string[] restorations = new JavaScriptSerializer().Deserialize<string[]>(File.ReadAllText(queryLog, Encoding.UTF8));
            if (restorations == null)
            {
                throw new InvalidOperationException("Update recovery inspection returned no decision.");
            }
            File.Delete(queryLog);
            if (restorations.Length == 0)
            {
                CompleteTerminalRecovery(paths);
                return null;
            }
            return RequireTransactionPath(paths, restorations[0]);
        }

        private static void RecoverAbandonedInstallationOwnership(LauncherPaths paths)
        {
            string lockRoot = Path.Combine(paths.RootDirectory, "data", "state", "locks");
            string installLock = Path.Combine(lockRoot, "soai.install.lock.d");
            string runtimeLock = Path.Combine(lockRoot, "soai.runtime.lock.d");
            if (!Directory.Exists(LauncherPaths.ToNativeFilesystemPath(installLock))
                && !Directory.Exists(LauncherPaths.ToNativeFilesystemPath(runtimeLock))) { return; }
            using (Mutex coordinator = NativeFilesystemHandles.OpenInstallerBootstrapGate(paths.RootDirectory))
            {
                List<SafeFileHandle> ancestors = NativeFilesystemHandles.RetainDirectoryAncestors(lockRoot);
                try
                {
                    ancestors.AddRange(NativeFilesystemHandles.RetainDirectoryAncestors(Path.Combine(paths.RootDirectory, "data", "locks")));
                    string manifestPath = Path.Combine(paths.RootDirectory, ".soai_install_manifest.json");
                    if (Directory.Exists(LauncherPaths.ToNativeFilesystemPath(manifestPath)))
                    { throw new InvalidOperationException("Installation identity storage is invalid; preserve its evidence for repair."); }
                    if (File.Exists(LauncherPaths.ToNativeFilesystemPath(manifestPath)))
                    {
                        if ((File.GetAttributes(LauncherPaths.ToNativeFilesystemPath(manifestPath)) & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0)
                        { throw new InvalidOperationException("Installation identity storage is invalid; preserve its evidence for repair."); }
                        Dictionary<string, object> identity = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(File.ReadAllText(LauncherPaths.ToNativeFilesystemPath(manifestPath), Encoding.UTF8));
                        if (identity == null || !identity.ContainsKey("schema_version") || !identity.ContainsKey("product") || !identity.ContainsKey("edition")
                            || !object.Equals(identity["schema_version"], 1) || !object.Equals(identity["product"], "SoAI") || !object.Equals(identity["edition"], "soai-core"))
                        { throw new InvalidOperationException("Installation identity prevents abandoned ownership recovery; preserve its evidence for repair."); }
                    }
                    else if (!File.Exists(LauncherPaths.ToNativeFilesystemPath(Path.Combine(paths.RootDirectory, "backend", "main.py"))))
                    { throw new InvalidOperationException("Installation identity is unavailable; preserve abandoned ownership evidence for repair."); }
                    using (FileStream ownership = new FileStream(LauncherPaths.ToNativeFilesystemPath(Path.Combine(paths.RootDirectory, "data", "locks", "soai.installation.transaction.lock")), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.ReadWrite))
                    {
                        ownership.Lock(0, 1);
                        if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("SOAI_INSTALL_LOCK_HELD_PATH")))
                        {
                            NativeFilesystemHandles.RecoverAbandonedInstallLock(installLock);
                            if (Directory.Exists(LauncherPaths.ToNativeFilesystemPath(installLock)))
                            { throw new InvalidOperationException("A live installation owner prevents startup recovery. Finish its operation before retrying."); }
                        }
                        NativeFilesystemHandles.RecoverAbandonedInstallLock(runtimeLock);
                        if (Directory.Exists(LauncherPaths.ToNativeFilesystemPath(runtimeLock)))
                        { throw new InvalidOperationException("A live runtime owner prevents startup recovery. Stop the owned instance before retrying."); }
                    }
                }
                finally { foreach (SafeFileHandle ancestor in ancestors) { ancestor.Dispose(); } }
            }
        }

        public static string RequireTransactionPath(LauncherPaths paths, string transactionPath)
        {
            string fullPath = string.IsNullOrEmpty(transactionPath) ? string.Empty : Path.GetFullPath(transactionPath);
            if (!string.Equals(Path.GetDirectoryName(fullPath), paths.RootDirectory, StringComparison.OrdinalIgnoreCase)
                || !Path.GetFileName(fullPath).StartsWith(TransactionPrefix, StringComparison.Ordinal))
            {
                throw new InvalidOperationException("The interrupted update restoration target is invalid; preserve the installation for repair.");
            }
            return fullPath;
        }

        public static bool IsRestorationCommand(string[] args)
        {
            return args != null && args.Length >= 3 && string.Equals(args[0], RestorationArgument, StringComparison.Ordinal);
        }

        public static void RequestRestoration(LauncherPaths paths, string transactionPath, string[] relaunchArguments)
        {
            List<string> arguments = new List<string> { RestorationArgument, RequireTransactionPath(paths, transactionPath) };
            using (Process launcher = Process.GetCurrentProcess())
            {
                arguments.Add(launcher.Id.ToString(CultureInfo.InvariantCulture));
            }
            arguments.AddRange(relaunchArguments);
            ProcessStartInfo startInfo = new ProcessStartInfo();
            startInfo.FileName = NativeBackendJob.ResolveProcessPath(NativeBackendJob.ReadProcessImagePath(NativeBackendJob.GetCurrentProcess()));
            startInfo.Arguments = BackendProcess.BuildArgumentString(arguments.ToArray()).TrimStart();
            startInfo.WorkingDirectory = NativeBackendJob.ResolveProcessPath(paths.RootDirectory, true);
            startInfo.UseShellExecute = true;
            startInfo.Verb = "runas";
            try
            {
                using (Process.Start(startInfo))
                {
                }
            }
            catch (Win32Exception exception)
            {
                if (exception.NativeErrorCode == 1223)
                {
                    throw new InvalidOperationException("SoAI must restore the previous version after an interrupted update. Start SoAI again and approve the administrator prompt to continue.", exception);
                }
                throw;
            }
        }

        public static int RunRestoration(LauncherPaths paths, string[] args)
        {
            try
            {
                if (!PrivilegeState.IsElevated())
                {
                    throw new InvalidOperationException("Interrupted update restoration requires administrator access.");
                }
                string transactionPath = RequireTransactionPath(paths, args[1]);
                if (!Directory.Exists(transactionPath))
                {
                    throw new DirectoryNotFoundException("The interrupted update transaction is missing; preserve the installation for repair.");
                }
                int requestingLauncher;
                if (!int.TryParse(args[2], NumberStyles.None, CultureInfo.InvariantCulture, out requestingLauncher))
                {
                    throw new InvalidOperationException("The restoration request does not identify its launcher.");
                }
                try
                {
                    using (Process launcher = Process.GetProcessById(requestingLauncher))
                    {
                        if (!launcher.WaitForExit((int)RestorationHandoffTimeout.TotalMilliseconds))
                        {
                            throw new TimeoutException("The requesting SoAI window did not close before restoration.");
                        }
                    }
                }
                catch (ArgumentException)
                {
                }
                if (!ServiceRegistration.WaitForStopped(paths.RootDirectory, RestorationHandoffTimeout))
                {
                    throw new TimeoutException("The SoAI service did not stop before restoration.");
                }
                string[] relaunchArguments = new string[args.Length - 3];
                Array.Copy(args, 3, relaunchArguments, 0, relaunchArguments.Length);
                StartRestorationSupervisor(paths, transactionPath, relaunchArguments);
                return 0;
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                MessageBox.Show("SoAI could not recover the interrupted update. Your recovery files have been retained. Close other SoAI windows and try again. If recovery still fails, keep the installation for repair.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }

        private static void StartRestorationSupervisor(LauncherPaths paths, string transactionPath, string[] relaunchArguments)
        {
            string recoveryScript = Path.Combine(transactionPath, "old", "backend", "app", "updater", "windows_installer_handoff.ps1");
            if (!File.Exists(recoveryScript))
            {
                throw new FileNotFoundException("The retained update recovery supervisor is missing.", recoveryScript);
            }
            string readyPath = Path.Combine(transactionPath, "launcher-recovery-" + Guid.NewGuid().ToString("N") + ".ready");
            using (Process launcher = Process.GetCurrentProcess())
            {
                ProcessStartInfo startInfo = new ProcessStartInfo();
                startInfo.FileName = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0", "powershell.exe");
                startInfo.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File " + BackendProcess.Quote(recoveryScript)
                    + " -InstallRoot " + BackendProcess.Quote(paths.RootDirectory)
                    + " -TransactionPath " + BackendProcess.Quote(transactionPath)
                    + " -ReadyPath " + BackendProcess.Quote(readyPath)
                    + " -RecoveryLauncherPid " + launcher.Id.ToString(CultureInfo.InvariantCulture)
                    + " -RecoveryLauncherStartTicks " + launcher.StartTime.ToUniversalTime().Ticks.ToString(CultureInfo.InvariantCulture);
                if (relaunchArguments.Length > 0)
                {
                    startInfo.Arguments += " -RelaunchArguments " + BackendProcess.Quote(BackendProcess.BuildArgumentString(relaunchArguments));
                }
                startInfo.WorkingDirectory = NativeBackendJob.ResolveProcessPath(paths.RootDirectory, true);
                startInfo.UseShellExecute = true;
                startInfo.Verb = "runas";
                startInfo.WindowStyle = ProcessWindowStyle.Hidden;
                using (Process supervisor = Process.Start(startInfo))
                {
                    if (supervisor == null)
                    {
                        throw new InvalidOperationException("The update recovery supervisor did not start.");
                    }
                    IntPtr supervisorHandle = supervisor.Handle;
                    Stopwatch deadline = Stopwatch.StartNew();
                    while (!supervisor.HasExited && deadline.Elapsed < TimeSpan.FromMinutes(2))
                    {
                        if (File.Exists(readyPath))
                        {
                            string acknowledgement = File.ReadAllText(readyPath, Encoding.UTF8).Trim();
                            if (supervisorHandle == IntPtr.Zero || acknowledgement != supervisor.Id.ToString(CultureInfo.InvariantCulture))
                            {
                                throw new InvalidOperationException("The recovery acknowledgement does not identify its supervisor.");
                            }
                            return;
                        }
                        Thread.Sleep(100);
                    }
                    throw new InvalidOperationException("The update recovery supervisor did not acknowledge exclusive ownership.");
                }
            }
        }
    }

    internal static class LauncherCommand
    {
        private const string ElevatedConsoleHandoffArgument = "--soai-elevated-console-command";
        public const string AfterUpdateArgument = "--soai-after-update";

        public static string[] NormalizeCompleteInstallArguments(string[] args)
        {
            if (args == null || args.Length == 0 || args[0] != "--soai-complete-install")
            {
                return args;
            }
            List<string> arguments = new List<string>(args);
            arguments.RemoveAt(0);
            int commandIndex = -1;
            for (int index = 0; index < arguments.Count; index++)
            {
                string argument = arguments[index].ToLowerInvariant();
                if (argument == "--target" || argument == "-target" || argument == "--status-file" || argument == "-status-file")
                {
                    index++;
                    continue;
                }
                if (IsInstallCommand(argument))
                {
                    commandIndex = index;
                    break;
                }
            }
            string command = commandIndex < 0 ? "install" : arguments[commandIndex];
            if (commandIndex >= 0)
            {
                arguments.RemoveAt(commandIndex);
            }
            arguments.Insert(0, command);
            return arguments.ToArray();
        }

        public static bool IsAfterUpdateLaunch(string[] args)
        {
            return args != null && Array.Exists(args, delegate(string value) { return string.Equals(value, AfterUpdateArgument, StringComparison.Ordinal); });
        }

        public static string[] RemoveAfterUpdateArgument(string[] args)
        {
            return Array.FindAll(args ?? new string[0], delegate(string value) { return !string.Equals(value, AfterUpdateArgument, StringComparison.Ordinal); });
        }

        public static bool IsConsoleCommand(string[] args)
        {
            string first = FirstArgument(args);
            return IsInstallCommand(first)
                || first == "status"
                || first == "--status"
                || first == "-status"
                || first == "stop"
                || first == "--stop"
                || first == "-stop"
                || first == "restart"
                || first == "--restart"
                || first == "-restart"
                || first == "version"
                || first == "--version"
                || first == "-version"
                || first == "help"
                || first == "--help"
                || first == "-help"
                || first == "-h";
        }

        public static bool IsInstallCommand(string[] args)
        {
            return IsInstallCommand(FirstArgument(args));
        }

        public static bool IsInstallDepsCommand(string[] args)
        {
            string first = FirstArgument(args);
            return first == "install-deps" || first == "--install-deps" || first == "-install-deps";
        }

        public static bool IsStopCommand(string[] args)
        {
            string first = FirstArgument(args);
            return first == "stop" || first == "--stop" || first == "-stop";
        }

        public static bool RequiresAdministrator(string[] args)
        {
            string first = FirstArgument(args);
            return IsInstallCommand(first)
                || first == "stop"
                || first == "--stop"
                || first == "-stop"
                || first == "restart"
                || first == "--restart"
                || first == "-restart";
        }

        public static bool IsElevatedConsoleHandoff(string[] args)
        {
            return args != null
                && args.Length > 1
                && string.Equals(args[0], ElevatedConsoleHandoffArgument, StringComparison.Ordinal);
        }

        public static string[] RemoveElevatedConsoleHandoff(string[] args)
        {
            string[] commandArguments = new string[args.Length - 1];
            Array.Copy(args, 1, commandArguments, 0, commandArguments.Length);
            return commandArguments;
        }

        public static string BuildElevatedConsoleHandoffArguments(string[] args)
        {
            return BackendProcess.Quote(ElevatedConsoleHandoffArgument)
                + BackendProcess.BuildArgumentString(args);
        }

        private static string FirstArgument(string[] args)
        {
            if (args == null || args.Length == 0)
            {
                return string.Empty;
            }
            return (args[0] ?? string.Empty).Trim().ToLowerInvariant();
        }

        private static bool IsInstallCommand(string first)
        {
            return first == "install"
                || first == "--install"
                || first == "-install"
                || first == "install-deps"
                || first == "--install-deps"
                || first == "-install-deps";
        }
    }

    internal sealed class LauncherForm : Form
    {
        private static readonly TimeSpan BackendStartupTimeout = TimeSpan.FromMinutes(20);
        private static readonly TimeSpan UpdateShutdownTimeout = TimeSpan.FromMinutes(15);
        private static readonly TimeSpan UpdateInstallTimeout = TimeSpan.FromMinutes(120);
        private static readonly TimeSpan UpdateProbeInterval = TimeSpan.FromSeconds(1);
        private const string FinishingUpdateStatus = "Finishing the SoAI update...";

        private readonly LauncherPaths paths;
        private readonly bool afterUpdate;
        private readonly SplashView splash;
        private readonly WebView2 webView;
        private readonly CancellationTokenSource shutdownToken;
        private CoreWebView2Environment webViewEnvironment;
        private EndpointInfo activeEndpoint;
        private BackendServiceSession backendSession;
        private LauncherAppearance appearance;
        private bool lightTheme;
        private TaskCompletionSource<bool> frontendRevealed;
        private readonly SemaphoreSlim navigationGate = new SemaphoreSlim(1, 1);
        private volatile string activeNavigationAttempt;
        private Task<string> readinessEvaluation;
        private string readinessEvaluationAttempt;
        private volatile bool closeRequested;
        private bool closeCompleted;
        private Task startupTask;
        private Task updateHandoffTask;
        private Task endpointMonitorTask;
        private readonly List<DetachedEndpointNavigation> detachedEndpointNavigations = new List<DetachedEndpointNavigation>();
        private string pendingEndpointRoute;
        private bool endpointNavigationFailureReported;
        private bool startupWindowRevealed;
        private string updateHandoffVersion;

        public int ExitCode { get; private set; }
        internal DesktopWindowSession DesktopSession { get; set; }

        internal bool CanActivateDesktop
        {
            get { return !closeRequested && !DesktopSession.IsClosing && Opacity > 0D && ShowInTaskbar; }
        }

        public LauncherForm(LauncherPaths paths, bool afterUpdate)
        {
            this.paths = paths;
            this.afterUpdate = afterUpdate;
            this.shutdownToken = new CancellationTokenSource();
            this.ExitCode = 0;
            this.appearance = LauncherAppearance.Load(LauncherPaths.UserStateDirectory);
            this.lightTheme = appearance.IsLight;

            this.Text = "SoAI";
            this.StartPosition = FormStartPosition.CenterScreen;
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.MinimumSize = new Size(980, 680);
            this.Size = new Size(1320, 860);
            this.BackColor = LauncherAppearance.BackgroundFor(lightTheme);
            this.Icon = paths.TryLoadIcon();
            this.Opacity = 0D;
            this.ShowInTaskbar = false;
            this.HandleCreated += delegate { LauncherAppearance.ApplyToWindow(this, lightTheme); };

            this.webView = new WebView2();
            this.webView.Dock = DockStyle.Fill;
            this.webView.Visible = true;
            this.webView.DefaultBackgroundColor = LauncherAppearance.BackgroundFor(lightTheme);
            this.Controls.Add(this.webView);

            this.splash = new SplashView(paths, lightTheme, appearance.InterfaceScale);
            this.splash.Dock = DockStyle.Fill;
            this.Controls.Add(this.splash);
            this.splash.BringToFront();

            this.FormClosing += OnFormClosing;
            this.Shown += async delegate { startupTask = StartAsync(); await startupTask; };
        }

        private async Task StartAsync()
        {
            if (closeRequested)
            {
                return;
            }
            try
            {
                LauncherDiagnostics.ClearStartupFailure();
                splash.SetStatus(afterUpdate ? FinishingUpdateStatus : "Preparing the app window...");
                Task webViewStartup = EnsureWebViewAsync();
                Task<EndpointInfo> backendStartup = EnsureBackendAsync(shutdownToken.Token, webViewStartup);
                await Task.WhenAll(webViewStartup, backendStartup);
                if (afterUpdate)
                {
                    await webView.CoreWebView2.Profile.ClearBrowsingDataAsync(CoreWebView2BrowsingDataKinds.DiskCache);
                }

                splash.SetStatus(afterUpdate ? FinishingUpdateStatus : "Starting SoAI...");
                EndpointInfo endpoint = await backendStartup;
                activeEndpoint = endpoint;

                splash.SetStatus(afterUpdate ? FinishingUpdateStatus : "Preparing the app window...");
                await NavigateAndRevealAsync(endpoint, shutdownToken.Token);
                endpointMonitorTask = MonitorEndpointAsync(shutdownToken.Token);
            }
            catch (OperationCanceledException)
            {
                ExitCode = 0;
                if (!closeRequested)
                {
                    CloseQuietly();
                }
            }
            catch (UpdateRestorationRequiredException restoration)
            {
                try
                {
                    UpdateRecovery.RequestRestoration(paths, restoration.TransactionPath, afterUpdate ? new string[] { LauncherCommand.AfterUpdateArgument } : new string[0]);
                    ExitCode = 0;
                    CloseQuietly();
                }
                catch (Exception ex)
                {
                    ShowStartupFailure(ex);
                }
            }
            catch (Exception ex)
            {
                ShowStartupFailure(ex);
            }
        }

        private void ShowStartupFailure(Exception ex)
        {
            ExitCode = 1;
            string diagnosticPath = LauncherDiagnostics.WriteStartupFailure(paths, ex);
            RevealStartupWindow();
            splash.ShowFailure(BuildStartupFailureMessage(ex, diagnosticPath));
        }

        private void RevealStartupWindow()
        {
            if (startupWindowRevealed)
            {
                return;
            }
            startupWindowRevealed = true;
            splash.Reveal();
            ShowInTaskbar = true;
            Opacity = 1D;
            Activate();
        }

        private static string BuildStartupFailureMessage(Exception ex, string diagnosticPath)
        {
            string message = ex == null ? "Unknown startup failure." : ex.Message;
            if (string.IsNullOrWhiteSpace(diagnosticPath))
            {
                return message;
            }
            return message + Environment.NewLine + Environment.NewLine + "Full details were written to:" + Environment.NewLine + diagnosticPath;
        }

        private async Task<EndpointInfo> EnsureBackendAsync(CancellationToken token, Task webViewStartup)
        {
            EndpointInfo existingEndpoint = await DiscoveryProbe.TryResolveAsync(token);
            bool existingReady = existingEndpoint != null && await HealthProbe.IsReadyAsync(existingEndpoint, token);
            BackendServiceSession session = await BackendServiceSession.OpenAsync(paths, token);
            try
            {
                backendSession = session;
                await webViewStartup;
                if (existingReady)
                {
                    activeEndpoint = existingEndpoint;
                    RevealStartupWindow();
                    splash.SetStatus(afterUpdate ? FinishingUpdateStatus : "SoAI is already running...");
                }
                RevealStartupWindow();
                NativeImageAllowance readiness = await Task.Run(delegate { return paths.ManagedRuntimeReadinessAllowance(BackendStartupTimeout); });
                return await session.WaitForReadyAsync(splash, readiness, token);
            }
            catch
            {
                if (ReferenceEquals(backendSession, session))
                {
                    backendSession = null;
                    session.Dispose();
                }
                throw;
            }
        }

        private async Task EnsureWebViewAsync()
        {
            try
            {
                string browserExecutableFolder = paths.ResolveWebView2RuntimeDirectory();
                EnsureWebViewRuntimeAvailable(browserExecutableFolder);
                string userDataFolder = Path.Combine(LauncherPaths.UserStateDirectory, "launcher-webview2", LauncherPaths.StableRootIdentity(paths.RootDirectory));
                Directory.CreateDirectory(userDataFolder);
                string resolvedBrowserExecutableFolder = string.IsNullOrWhiteSpace(browserExecutableFolder) ? null : browserExecutableFolder;
                CoreWebView2EnvironmentOptions options = new CoreWebView2EnvironmentOptions(
                    "--force-prefers-no-reduced-motion " +
                    "--disable-renderer-backgrounding " +
                    "--disable-backgrounding-occluded-windows " +
                    "--disable-background-timer-throttling");
                try
                {
                    webViewEnvironment = await CoreWebView2Environment.CreateAsync(resolvedBrowserExecutableFolder, userDataFolder, options);
                    await webView.EnsureCoreWebView2Async(webViewEnvironment);
                }
                catch (Exception ex)
                {
                    throw new InvalidOperationException("The Microsoft Edge WebView2 Runtime is missing or damaged. Please reinstall SoAI.", ex);
                }
                await ConfigureWebViewAsync(webView, this, true);
                await splash.AttachWebViewAsync(webViewEnvironment);
            }
            catch
            {
                shutdownToken.Cancel();
                throw;
            }
        }

        private async Task ConfigureWebViewAsync(WebView2 targetWebView, Form hostForm, bool mainWindow)
        {
            CoreWebView2 core = targetWebView.CoreWebView2;
            core.Settings.AreDevToolsEnabled = false;
            core.Settings.AreDefaultContextMenusEnabled = true;
            core.Settings.AreBrowserAcceleratorKeysEnabled = true;
            core.ServerCertificateErrorDetected += delegate(object sender, CoreWebView2ServerCertificateErrorDetectedEventArgs e)
            {
                if (LoopbackCertificatePolicy.IsLoopbackUri(e.RequestUri))
                {
                    e.Action = CoreWebView2ServerCertificateErrorAction.AlwaysAllow;
                }
            };
            core.PermissionRequested += delegate(object sender, CoreWebView2PermissionRequestedEventArgs e)
            {
                HandlePermissionRequest(e);
            };
            core.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e)
            {
                HandleNavigationStarting(e, hostForm);
            };
            core.NewWindowRequested += async delegate(object sender, CoreWebView2NewWindowRequestedEventArgs e)
            {
                await HandleNewWindowRequestedAsync(e, hostForm);
            };
            core.DownloadStarting += delegate(object sender, CoreWebView2DownloadStartingEventArgs e)
            {
                HandleDownloadStarting(e, hostForm);
            };
            core.ContainsFullScreenElementChanged += delegate
            {
                FullScreenMode.Set(hostForm, core.ContainsFullScreenElement);
            };
            if (mainWindow)
            {
                await DesktopLauncherBridge.AttachAsync(core, IsTrustedContentUri, BeginUpdateHandoff, SignalFrontendRevealed, ApplyWebAppearance);
            }
            else
            {
                await core.AddScriptToExecuteOnDocumentCreatedAsync(DesktopLauncherBridge.CapabilityScript);
            }
            await core.AddScriptToExecuteOnDocumentCreatedAsync(
                "(function(){try{document.documentElement.style.webkitFontSmoothing='auto';document.documentElement.setAttribute('data-animation-speed','normal');document.documentElement.removeAttribute('data-transition-level');document.addEventListener('DOMContentLoaded',function(){document.body&&document.body.classList.remove('reduce-motions');},{once:true});}catch(e){}})();");
            core.DocumentTitleChanged += delegate
            {
                string title = core.DocumentTitle;
                if (!string.IsNullOrWhiteSpace(title))
                {
                    hostForm.Text = title;
                }
            };
            core.ProcessFailed += delegate(object sender, CoreWebView2ProcessFailedEventArgs e)
            {
                if (mainWindow)
                {
                    if (e.ProcessFailedKind == CoreWebView2ProcessFailedKind.BrowserProcessExited)
                    {
                        splash.DetachWebView();
                    }
                    splash.ShowFailure("The embedded web view stopped unexpectedly: " + e.ProcessFailedKind.ToString());
                    splash.Visible = true;
                    splash.BringToFront();
                }
                else if (!hostForm.IsDisposed)
                {
                    hostForm.Close();
                }
            };
        }

        private void HandlePermissionRequest(CoreWebView2PermissionRequestedEventArgs e)
        {
            bool trusted = IsTrustedContentUri(e.Uri);
            bool allowed = trusted && IsAllowedSoAIPermission(e.PermissionKind);
            e.State = allowed ? CoreWebView2PermissionState.Allow : CoreWebView2PermissionState.Deny;
            e.SavesInProfile = false;
            e.Handled = true;
        }

        private void HandleNavigationStarting(CoreWebView2NavigationStartingEventArgs e, Form hostForm)
        {
            if (IsEmbeddedContentUri(e.Uri))
            {
                DetachedWebViewForm detached = hostForm as DetachedWebViewForm;
                if (detached != null && IsTrustedContentUri(e.Uri))
                {
                    detached.Reveal();
                }
                return;
            }

            e.Cancel = true;
            if (activeEndpoint != null && activeEndpoint.IsTransportChangeUri(e.Uri)) return;
            TrustedWebContent.TryOpenExternalUri(e.Uri, e.IsUserInitiated);
        }

        private static bool IsAllowedSoAIPermission(CoreWebView2PermissionKind kind)
        {
            return kind == CoreWebView2PermissionKind.Microphone
                || kind == CoreWebView2PermissionKind.Camera
                || kind == CoreWebView2PermissionKind.Notifications
                || kind == CoreWebView2PermissionKind.ClipboardRead
                || kind == CoreWebView2PermissionKind.MultipleAutomaticDownloads
                || kind == CoreWebView2PermissionKind.FileReadWrite
                || kind == CoreWebView2PermissionKind.Autoplay
                || kind == CoreWebView2PermissionKind.PersistentStorage;
        }

        private async Task HandleNewWindowRequestedAsync(CoreWebView2NewWindowRequestedEventArgs e, Form owner)
        {
            e.Handled = true;
            string uri = e.Uri ?? string.Empty;
            if (!IsEmbeddedContentUri(uri))
            {
                if (activeEndpoint != null && activeEndpoint.IsTransportChangeUri(uri)) return;
                TrustedWebContent.TryOpenExternalUri(uri, e.IsUserInitiated);
                return;
            }

            CoreWebView2Deferral deferral = e.GetDeferral();
            DetachedWebViewForm window = null;
            try
            {
                window = new DetachedWebViewForm(owner.Icon, lightTheme);
                DesktopSession.RegisterDetachedWindow(window);
                await window.InitializeAsync(webViewEnvironment);
                if (DesktopSession.IsClosing || window.IsDisposed) { return; }
                await ConfigureWebViewAsync(window.WebView, window, false);
                if (DesktopSession.IsClosing || window.IsDisposed) { return; }
                e.NewWindow = window.WebView.CoreWebView2;
                if (TrustedWebContent.IsBlankWindowUri(uri))
                {
                    window.ShowHidden();
                }
                else
                {
                    window.Show();
                }
            }
            catch
            {
                if (window != null && !window.IsDisposed)
                {
                    window.Close();
                    if (!window.IsDisposed && !window.Visible)
                    {
                        window.Dispose();
                    }
                }
            }
            finally
            {
                deferral.Complete();
            }
        }

        private bool IsTrustedContentUri(string uri)
        {
            EndpointInfo endpoint = activeEndpoint;
            if (endpoint != null)
            {
                return endpoint.IsSameOrigin(uri);
            }
            return TrustedWebContent.IsTrustedAppUri(uri);
        }

        private bool IsEmbeddedContentUri(string uri)
        {
            return TrustedWebContent.IsBlankWindowUri(uri) || IsTrustedContentUri(uri) || TrustedWebContent.IsWebViewGeneratedContentUri(uri);
        }

        private static void HandleDownloadStarting(CoreWebView2DownloadStartingEventArgs e, Form hostForm)
        {
            try
            {
                DetachedWebViewForm detached = hostForm as DetachedWebViewForm;
                bool hiddenPopupDownload = detached != null && detached.HiddenUntilContent;
                string directory = DownloadTargets.ResolveDownloadDirectory();
                Directory.CreateDirectory(directory);
                string fileName = DownloadTargets.ResolveFileName(e);
                e.ResultFilePath = DownloadTargets.ResolveUniquePath(directory, fileName);
                e.Cancel = false;
                e.Handled = hiddenPopupDownload;
                if (hiddenPopupDownload && e.DownloadOperation != null)
                {
                    CloseHiddenPopupAfterDownload(e.DownloadOperation, detached);
                }
            }
            catch
            {
                e.Handled = false;
            }
        }

        private static void CloseHiddenPopupAfterDownload(CoreWebView2DownloadOperation operation, DetachedWebViewForm window)
        {
            EventHandler<object> stateChanged = null;
            stateChanged = delegate
            {
                if (string.Equals(operation.State.ToString(), "InProgress", StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
                operation.StateChanged -= stateChanged;
                if (window == null || window.IsDisposed)
                {
                    return;
                }
                try
                {
                    window.BeginInvoke(new MethodInvoker(delegate
                    {
                        if (!window.IsDisposed && window.HiddenUntilContent)
                        {
                            window.Close();
                        }
                    }));
                }
                catch
                {
                }
            };
            operation.StateChanged += stateChanged;
            stateChanged(operation, null);
        }

        private static void EnsureWebViewRuntimeAvailable(string browserExecutableFolder)
        {
            try
            {
                string resolvedBrowserExecutableFolder = string.IsNullOrWhiteSpace(browserExecutableFolder) ? null : browserExecutableFolder;
                string version = CoreWebView2Environment.GetAvailableBrowserVersionString(resolvedBrowserExecutableFolder);
                if (string.IsNullOrWhiteSpace(version))
                {
                    throw new InvalidOperationException("WebView2 version was not reported.");
                }
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException("The Microsoft Edge WebView2 Runtime is missing or damaged. Please reinstall SoAI.", ex);
            }
        }

        private async Task<EndpointInfo> ResolveProfileEndpointAsync(EndpointInfo endpoint, CancellationToken token)
        {
            string cookieName = endpoint.AuthenticationCookieName;
            var cookies = await webView.CoreWebView2.CookieManager.GetCookiesAsync(endpoint.BaseUrl);
            token.ThrowIfCancellationRequested();
            if (cookies.Any(cookie => cookie.Name == cookieName && !string.IsNullOrEmpty(cookie.Value)))
            {
                return endpoint;
            }
            // Retain sessions issued before discovery used a stable host preference.
            EndpointInfo alternate = new EndpointInfo(endpoint.Scheme,
                endpoint.Host == "127.0.0.1" ? "localhost" : "127.0.0.1", endpoint.Port);
            var alternateCookies = await webView.CoreWebView2.CookieManager.GetCookiesAsync(alternate.BaseUrl);
            token.ThrowIfCancellationRequested();
            if (alternateCookies.Any(cookie => cookie.Name == cookieName && !string.IsNullOrEmpty(cookie.Value))
                && await HealthProbe.IsReadyAsync(alternate, token))
            {
                return alternate;
            }
            return endpoint;
        }

        private async Task NavigateAndRevealAsync(EndpointInfo endpoint, CancellationToken token)
        {
            await navigationGate.WaitAsync(token);
            try
            {
                token.ThrowIfCancellationRequested();
                endpoint = await ResolveProfileEndpointAsync(endpoint, token);
                string destination = pendingEndpointRoute == null
                    ? endpoint.RebaseAppUri(webView.CoreWebView2.Source, activeEndpoint) ?? endpoint.BaseUrl
                    : endpoint.BaseUrl.TrimEnd('/') + pendingEndpointRoute;
                activeEndpoint = endpoint;
                CoreWebView2 core = webView.CoreWebView2;
                for (int attempt = 0; attempt < 2; attempt++)
                {
                    token.ThrowIfCancellationRequested();
                    string navigationAttempt = Guid.NewGuid().ToString("N");
                    activeNavigationAttempt = navigationAttempt;
                    splash.SetStatus(attempt == 0 ? "Opening SoAI..." : "Reopening the app window...");
                    frontendRevealed = new TaskCompletionSource<bool>();
                    string attemptScript = null;
                    string bootHandoffScript = null;
                    ulong? navigationId = null;
                    bool certificateDecisionPending = false;
                    TaskCompletionSource<bool> navigation = new TaskCompletionSource<bool>();
                    ExceptionDispatchInfo navigationTimeout = null;
                    EventHandler<CoreWebView2NavigationStartingEventArgs> starting = delegate(object sender, CoreWebView2NavigationStartingEventArgs eventArguments)
                    {
                        if (activeNavigationAttempt == navigationAttempt && endpoint.IsSameOrigin(eventArguments.Uri))
                        {
                            if (navigationId.HasValue && navigationId.Value != eventArguments.NavigationId && !certificateDecisionPending)
                            {
                                navigation.TrySetException(new InvalidOperationException("The app window navigation was superseded."));
                            }
                            else
                            {
                                navigationId = eventArguments.NavigationId;
                                certificateDecisionPending = false;
                            }
                        }
                    };
                    EventHandler<CoreWebView2NavigationCompletedEventArgs> completed = delegate(object sender, CoreWebView2NavigationCompletedEventArgs eventArguments)
                    {
                        if (activeNavigationAttempt != navigationAttempt || !navigationId.HasValue || navigationId.Value != eventArguments.NavigationId)
                        {
                            return;
                        }
                        if (eventArguments.IsSuccess && endpoint.IsSameOrigin(core.Source))
                        {
                            navigation.TrySetResult(true);
                        }
                        else if (!eventArguments.IsSuccess && endpoint.Scheme == "https"
                            && IsCertificateNavigationFailure(eventArguments.WebErrorStatus))
                        {
                            certificateDecisionPending = true;
                        }
                        else
                        {
                            navigation.TrySetException(new InvalidOperationException("The SoAI WebUI failed to load: " + eventArguments.WebErrorStatus.ToString()));
                        }
                    };
                    try
                    {
                        bool reloadDocument = IsCurrentAppDocument(core.Source, destination);
                        string routeScript = BuildReloadRouteScript(destination, reloadDocument);
                        attemptScript = await core.AddScriptToExecuteOnDocumentCreatedAsync(
                            "Object.defineProperty(window,'soaiLauncherNavigationAttempt',{value:'" + navigationAttempt + "',writable:false,configurable:false});" + routeScript);
                        token.ThrowIfCancellationRequested();
                        bootHandoffScript = splash.UsesWebView
                            ? await core.AddScriptToExecuteOnDocumentCreatedAsync(splash.BuildBootHandoffScript())
                            : null;
                        token.ThrowIfCancellationRequested();
                        core.NavigationStarting += starting;
                        core.NavigationCompleted += completed;
                        if (reloadDocument) core.Reload();
                        else core.Navigate(destination);
                        await WaitForNavigationAsync(endpoint, navigation, token);
                        await WaitForFrontendReadyAsync(endpoint, navigationAttempt, frontendRevealed.Task, token);
                        break;
                    }
                    catch (TimeoutException exception)
                    {
                        navigationTimeout = ExceptionDispatchInfo.Capture(exception);
                    }
                    finally
                    {
                        activeNavigationAttempt = null;
                        core.NavigationStarting -= starting;
                        core.NavigationCompleted -= completed;
                        if (!webView.IsDisposed)
                        {
                            if (bootHandoffScript != null) core.RemoveScriptToExecuteOnDocumentCreated(bootHandoffScript);
                            if (attemptScript != null) core.RemoveScriptToExecuteOnDocumentCreated(attemptScript);
                        }
                    }
                    if (navigationTimeout != null)
                    {
                        if (attempt != 0 || !await HealthProbe.IsReadyAsync(endpoint, token))
                        {
                            navigationTimeout.Throw();
                        }
                        LauncherDiagnostics.WriteStartupFailure(paths, navigationTimeout.SourceException);
                    }
                }
                token.ThrowIfCancellationRequested();
                splash.BringToFront();
                await splash.ExitAsync(token);
                token.ThrowIfCancellationRequested();
                splash.Visible = false;
                ActiveControl = webView;
                webView.Select();
                webView.Focus();
                pendingEndpointRoute = null;
            }
            finally
            {
                navigationGate.Release();
            }
        }

        private async Task WaitForNavigationAsync(EndpointInfo endpoint, TaskCompletionSource<bool> navigation, CancellationToken token)
        {
            Stopwatch duration = Stopwatch.StartNew();
            TimeSpan? unhealthySince = null;
            using (token.Register(delegate { navigation.TrySetCanceled(); }))
            {
                while (duration.Elapsed < TimeSpan.FromSeconds(45))
                {
                    token.ThrowIfCancellationRequested();
                    Task completed = await Task.WhenAny(navigation.Task, Task.Delay(250, token));
                    if (completed == navigation.Task)
                    {
                        await navigation.Task;
                        return;
                    }
                    if (await HealthProbe.IsReadyAsync(endpoint, token))
                    {
                        unhealthySince = null;
                    }
                    else if (!unhealthySince.HasValue)
                    {
                        unhealthySince = duration.Elapsed;
                    }
                    else if (duration.Elapsed - unhealthySince.Value > TimeSpan.FromSeconds(5))
                    {
                        throw new InvalidOperationException("SoAI became unavailable while the app window was opening.");
                    }
                }
            }
            throw new TimeoutException("The SoAI WebUI did not finish opening within 45 seconds.");
        }

        private static bool IsCertificateNavigationFailure(CoreWebView2WebErrorStatus status)
        {
            return status == CoreWebView2WebErrorStatus.CertificateCommonNameIsIncorrect
                || status == CoreWebView2WebErrorStatus.CertificateExpired
                || status == CoreWebView2WebErrorStatus.ClientCertificateContainsErrors
                || status == CoreWebView2WebErrorStatus.CertificateRevoked
                || status == CoreWebView2WebErrorStatus.CertificateIsInvalid;
        }

        private static bool IsCurrentAppDocument(string source, string destination)
        {
            Uri current;
            Uri target;
            return Uri.TryCreate(source, UriKind.Absolute, out current)
                && Uri.TryCreate(destination, UriKind.Absolute, out target)
                && string.Equals(current.GetLeftPart(UriPartial.Authority), target.GetLeftPart(UriPartial.Authority), StringComparison.OrdinalIgnoreCase)
                && string.Equals(current.PathAndQuery, target.PathAndQuery, StringComparison.Ordinal);
        }

        private static string BuildReloadRouteScript(string destination, bool reloadDocument)
        {
            if (!reloadDocument) return string.Empty;
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            string origin = new Uri(destination).GetLeftPart(UriPartial.Authority);
            return "if(window===window.top&&location.origin===" + serializer.Serialize(origin) + ")history.replaceState(history.state,''," + serializer.Serialize(destination) + ");";
        }

        private async Task WaitForFrontendReadyAsync(EndpointInfo endpoint, string navigationAttempt, Task<bool> revealed, CancellationToken token)
        {
            Stopwatch duration = Stopwatch.StartNew();
            bool revealObserved = false;
            while (duration.Elapsed < TimeSpan.FromSeconds(60))
            {
                token.ThrowIfCancellationRequested();
                if (activeNavigationAttempt != navigationAttempt || webView.IsDisposed)
                {
                    throw new OperationCanceledException(token);
                }
                if (!revealObserved && revealed.IsCompleted)
                {
                    if (!await revealed)
                    {
                        throw new InvalidOperationException("The SoAI WebUI did not confirm that it became interactive.");
                    }
                    revealObserved = true;
                }
                if (readinessEvaluation == null)
                {
                    readinessEvaluationAttempt = navigationAttempt;
                    readinessEvaluation = webView.CoreWebView2.ExecuteScriptAsync(
                        "(function(){if(window.soaiLauncherNavigationAttempt!=='" + navigationAttempt + "')return false;var documentRoot=document.documentElement;var preloader=document.getElementById('page-preloader');var login=document.querySelector('form,input[name=\"username\"],#username,[autocomplete=\"username\"]');return !!(document.readyState==='complete' && ((!documentRoot || !documentRoot.hasAttribute('data-soai-boot-state')) || login) && (!preloader || !preloader.isConnected || preloader.classList.contains('page-preloader--exiting') || login));})()");
                    readinessEvaluation.ContinueWith(delegate(Task<string> evaluation)
                    {
                        AggregateException failure = evaluation.Exception;
                        if (failure != null && activeNavigationAttempt != navigationAttempt && !closeRequested)
                        {
                            LauncherDiagnostics.WriteStartupFailure(paths, failure);
                        }
                    }, CancellationToken.None, TaskContinuationOptions.OnlyOnFaulted | TaskContinuationOptions.ExecuteSynchronously, TaskScheduler.Default);
                }
                Task<string> scriptTask = readinessEvaluation;
                TimeSpan remaining = TimeSpan.FromSeconds(60) - duration.Elapsed;
                if (remaining <= TimeSpan.Zero) break;
                Task completed = await Task.WhenAny(scriptTask, Task.Delay(remaining < TimeSpan.FromSeconds(1) ? remaining : TimeSpan.FromSeconds(1), token));
                if (completed != scriptTask) continue;
                string evaluationAttempt = readinessEvaluationAttempt;
                readinessEvaluation = null;
                readinessEvaluationAttempt = null;
                if (evaluationAttempt != navigationAttempt)
                {
                    continue;
                }
                string result = await scriptTask;
                token.ThrowIfCancellationRequested();
                if (activeNavigationAttempt == navigationAttempt && endpoint.IsSameOrigin(webView.CoreWebView2.Source)
                    && string.Equals(result, "true", StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
                remaining = TimeSpan.FromSeconds(60) - duration.Elapsed;
                if (remaining > TimeSpan.Zero) await Task.Delay(remaining < TimeSpan.FromMilliseconds(250) ? remaining : TimeSpan.FromMilliseconds(250), token);
            }
            throw new TimeoutException("The SoAI WebUI loaded, but the app did not become interactive within 60 seconds.");
        }

        private async Task MonitorEndpointAsync(CancellationToken token)
        {
            int delayMilliseconds = 2000;
            int healthyObservations = 0;
            Random jitter = new Random();
            try
            {
                while (true)
                {
                    await Task.Delay(delayMilliseconds + jitter.Next(0, 250), token);
                    if (updateHandoffVersion != null) continue;
                    bool ready = await ReconnectEndpointAsync(token);
                    healthyObservations = ready ? Math.Min(healthyObservations + 1, 3) : 0;
                    if (!ready) delayMilliseconds = Math.Min(delayMilliseconds * 2, 10000);
                    else if (healthyObservations == 3) delayMilliseconds = 2000;
                }
            }
            catch (Exception exception)
            {
                if (exception is OperationCanceledException && token.IsCancellationRequested) return;
                string diagnosticPath = LauncherDiagnostics.WriteStartupFailure(paths, exception);
                ShowUpdateSplash("Reconnecting to SoAI...");
                splash.ShowFailure(BuildStartupFailureMessage(exception, diagnosticPath));
            }
        }

        private async Task<bool> ReconnectEndpointAsync(CancellationToken token)
        {
            EndpointInfo previous = activeEndpoint;
            if (previous == null) return true;
            if (await HealthProbe.IsReadyAsync(previous, token))
            {
                if (pendingEndpointRoute != null && !await ReconnectMainWindowAsync(previous, token)) return false;
                return await ReconnectDetachedWindowsAsync(token);
            }
            EndpointInfo discovered = await DiscoveryProbe.TryResolveAsync(token);
            if (discovered == null || previous.IsSameOrigin(discovered.BaseUrl)
                || !await HealthProbe.IsReadyAsync(discovered, token)) return false;
            token.ThrowIfCancellationRequested();
            if (updateHandoffVersion != null || !ReferenceEquals(previous, activeEndpoint)) return false;
            foreach (DetachedWebViewForm window in DesktopSession.DetachedWindows)
            {
                if (window.IsDisposed || window.WebView.IsDisposed || window.WebView.CoreWebView2 == null
                    || detachedEndpointNavigations.Any(pending => ReferenceEquals(pending.Window, window))) continue;
                CoreWebView2 detached = window.WebView.CoreWebView2;
                try
                {
                    if (!previous.IsSameOrigin(detached.Source)) continue;
                    string context = await detached.ExecuteScriptAsync("(function(){var request=new CustomEvent('soai:desktop-detached-context-capture',{detail:{context:null}});window.dispatchEvent(request);return request.detail.context;})()");
                    token.ThrowIfCancellationRequested();
                    if (window.IsDisposed || window.WebView.IsDisposed || !ReferenceEquals(detached, window.WebView.CoreWebView2)) continue;
                    detachedEndpointNavigations.Add(new DetachedEndpointNavigation { Window = window, Source = detached.Source, Endpoint = previous, Context = context });
                }
                catch (Exception)
                {
                    token.ThrowIfCancellationRequested();
                    if (!window.IsDisposed && !window.WebView.IsDisposed) throw;
                }
            }
            if (pendingEndpointRoute == null)
            {
                Uri destination = new Uri(discovered.RebaseAppUri(webView.CoreWebView2.Source, previous) ?? discovered.BaseUrl);
                pendingEndpointRoute = destination.PathAndQuery + destination.Fragment;
            }
            if (!await ReconnectMainWindowAsync(discovered, token)) return false;
            return await ReconnectDetachedWindowsAsync(token);
        }

        private async Task<bool> ReconnectMainWindowAsync(EndpointInfo endpoint, CancellationToken token)
        {
            ShowUpdateSplash("Reconnecting to SoAI...");
            try
            {
                await NavigateAndRevealAsync(endpoint, token);
                endpointNavigationFailureReported = false;
                return true;
            }
            catch (Exception exception)
            {
                token.ThrowIfCancellationRequested();
                if (!IsRecoverableNavigationFailure(exception)) throw;
                if (!endpointNavigationFailureReported)
                {
                    endpointNavigationFailureReported = true;
                    string diagnosticPath = LauncherDiagnostics.WriteStartupFailure(paths, exception);
                    splash.ShowFailure(BuildStartupFailureMessage(exception, diagnosticPath));
                }
                return false;
            }
        }

        private async Task<bool> ReconnectDetachedWindowsAsync(CancellationToken token)
        {
            if (detachedEndpointNavigations.Count == 0) return true;
            var cookies = await webView.CoreWebView2.CookieManager.GetCookiesAsync(activeEndpoint.BaseUrl);
            token.ThrowIfCancellationRequested();
            if (!cookies.Any(cookie => cookie.Name == activeEndpoint.AuthenticationCookieName && !string.IsNullOrEmpty(cookie.Value))) return false;
            string authenticated = await webView.CoreWebView2.ExecuteScriptAsync(
                "(function(){var header=document.querySelector('.header');return !!(document.querySelector('.page-content-ready')&&header&&!header.classList.contains('u-hidden')&&!document.querySelector('#username'));})()");
            token.ThrowIfCancellationRequested();
            if (authenticated != "true") return false;
            bool allReady = true;
            foreach (DetachedEndpointNavigation pending in detachedEndpointNavigations.ToArray())
            {
                DetachedWebViewForm window = pending.Window;
                if (window.IsDisposed || window.WebView.IsDisposed || window.WebView.CoreWebView2 == null)
                {
                    detachedEndpointNavigations.Remove(pending);
                    continue;
                }
                CoreWebView2 detached = window.WebView.CoreWebView2;
                string destination = activeEndpoint.RebaseAppUri(pending.Source, pending.Endpoint);
                if (destination == null) throw new InvalidOperationException("A detached window no longer belongs to the reconnecting SoAI endpoint.");
                string script = null;
                TaskCompletionSource<bool> navigation = new TaskCompletionSource<bool>();
                EventHandler<CoreWebView2NavigationCompletedEventArgs> completed = delegate(object sender, CoreWebView2NavigationCompletedEventArgs arguments)
                {
                    if (arguments.IsSuccess && activeEndpoint.IsSameOrigin(detached.Source)) navigation.TrySetResult(true);
                    else if (!arguments.IsSuccess && !IsCertificateNavigationFailure(arguments.WebErrorStatus)) navigation.TrySetException(new InvalidOperationException("The detached SoAI window failed to load: " + arguments.WebErrorStatus.ToString()));
                };
                FormClosedEventHandler closed = delegate { navigation.TrySetCanceled(); };
                try
                {
                    bool reloadDocument = IsCurrentAppDocument(detached.Source, destination);
                    string origin = new Uri(destination).GetLeftPart(UriPartial.Authority);
                    JavaScriptSerializer serializer = new JavaScriptSerializer();
                    string contextScript = pending.Context != null && pending.Context != "null"
                        ? "if(window===window.top&&location.origin===" + serializer.Serialize(origin) + ")Object.defineProperty(window,'soaiDesktopLauncherDetachedContext',{value:JSON.parse(" + serializer.Serialize(pending.Context) + "),configurable:true});"
                        : string.Empty;
                    script = await detached.AddScriptToExecuteOnDocumentCreatedAsync(BuildReloadRouteScript(destination, reloadDocument) + contextScript);
                    token.ThrowIfCancellationRequested();
                    detached.NavigationCompleted += completed;
                    window.FormClosed += closed;
                    if (reloadDocument) detached.Reload();
                    else detached.Navigate(destination);
                    await WaitForNavigationAsync(activeEndpoint, navigation, token);
                    detachedEndpointNavigations.Remove(pending);
                }
                catch (Exception exception)
                {
                    token.ThrowIfCancellationRequested();
                    if (window.IsDisposed)
                    {
                        detachedEndpointNavigations.Remove(pending);
                        continue;
                    }
                    if (!IsRecoverableNavigationFailure(exception)) throw;
                    if (!pending.FailureReported)
                    {
                        pending.FailureReported = true;
                        LauncherDiagnostics.WriteStartupFailure(paths, exception);
                    }
                    window.Text = "Reconnecting to SoAI...";
                    allReady = false;
                }
                finally
                {
                    detached.NavigationCompleted -= completed;
                    window.FormClosed -= closed;
                    if (script != null && !window.WebView.IsDisposed) detached.RemoveScriptToExecuteOnDocumentCreated(script);
                }
            }
            return allReady;
        }

        private static bool IsRecoverableNavigationFailure(Exception exception)
        {
            return exception is InvalidOperationException || exception is TimeoutException || exception is COMException;
        }

        private sealed class DetachedEndpointNavigation
        {
            public DetachedWebViewForm Window;
            public EndpointInfo Endpoint;
            public string Source;
            public string Context;
            public bool FailureReported;
        }

        private async void BeginUpdateHandoff(string targetVersion)
        {
            if (updateHandoffVersion != null || closeRequested)
            {
                return;
            }
            updateHandoffVersion = targetVersion;
            updateHandoffTask = MonitorUpdateHandoffAsync(activeEndpoint, targetVersion, shutdownToken.Token);
            await updateHandoffTask;
        }

        private async Task MonitorUpdateHandoffAsync(EndpointInfo endpoint, string targetVersion, CancellationToken token)
        {
            try
            {
                DateTime shutdownDeadline = DateTime.UtcNow.Add(UpdateShutdownTimeout);
                while (endpoint != null && await HealthProbe.IsReadyAsync(endpoint, token))
                {
                    if (DateTime.UtcNow >= shutdownDeadline)
                    {
                        updateHandoffVersion = null;
                        return;
                    }
                    await Task.Delay(UpdateProbeInterval, token);
                }
                if (UpdateProgressWindow.TryStart(paths, targetVersion))
                {
                    CloseQuietly();
                    return;
                }
                ShowUpdateSplash("Installing SoAI " + targetVersion + "..." + Environment.NewLine + "This window will close and SoAI will reopen automatically when the update is complete.");
                DateTime installDeadline = DateTime.UtcNow.Add(UpdateInstallTimeout);
                while (DateTime.UtcNow < installDeadline)
                {
                    await Task.Delay(UpdateProbeInterval, token);
                    EndpointInfo resumed = await DiscoveryProbe.TryResolveAsync(token);
                    if (resumed != null && await HealthProbe.IsReadyAsync(resumed, token))
                    {
                        updateHandoffVersion = null;
                        splash.SetStatus("Reconnecting to SoAI...");
                        await NavigateAndRevealAsync(resumed, token);
                        return;
                    }
                }
                splash.ShowFailure(
                    "SoAI did not come back after the update.",
                    "Close this window and start SoAI again. The update log is application_updater.log in the SoAI data\\logs folder.");
            }
            catch (OperationCanceledException)
            {
            }
            catch (Exception exception)
            {
                string diagnosticPath = LauncherDiagnostics.WriteStartupFailure(paths, exception);
                ShowUpdateSplash(FinishingUpdateStatus);
                splash.ShowFailure("SoAI could not reopen after the update.", BuildStartupFailureMessage(exception, diagnosticPath));
            }
        }

        private void ShowUpdateSplash(string status)
        {
            if (!Controls.Contains(splash))
            {
                Controls.Add(splash);
            }
            splash.Restart(status);
            splash.Visible = true;
            splash.BringToFront();
        }

        private void SignalFrontendRevealed()
        {
            TaskCompletionSource<bool> signal = frontendRevealed;
            if (signal != null)
            {
                signal.TrySetResult(true);
            }
        }

        private void ApplyWebAppearance(LauncherAppearance next, bool light)
        {
            if (!next.SameAs(appearance))
            {
                appearance = next;
                next.Save(LauncherPaths.UserStateDirectory);
            }
            lightTheme = light;
            LauncherAppearance.ApplyToWindow(this, light);
            webView.DefaultBackgroundColor = LauncherAppearance.BackgroundFor(light);
            splash.SetAppearance(light, next.InterfaceScale);
            foreach (DetachedWebViewForm window in DesktopSession.DetachedWindows)
            {
                window.ApplyTheme(light);
            }
        }

        private async void OnFormClosing(object sender, FormClosingEventArgs e)
        {
            if (closeCompleted)
            {
                return;
            }
            e.Cancel = true;
            if (closeRequested)
            {
                return;
            }

            if (DesktopSession.TryDismissMainWindow(e.CloseReason)) { return; }
            DesktopSession.BeginShutdown();

            closeRequested = true;
            shutdownToken.Cancel();
            await Task.Yield();
            if (startupTask != null) await startupTask;
            if (updateHandoffTask != null) await updateHandoffTask;
            if (endpointMonitorTask != null) await endpointMonitorTask;
            await navigationGate.WaitAsync();
            try
            {
                ReleaseBackend();
                CloseDetachedWindows();
                closeCompleted = true;
                Close();
            }
            finally
            {
                navigationGate.Release();
            }
        }

        internal void CloseQuietly()
        {
            if (closeRequested)
            {
                return;
            }
            DesktopSession.BeginShutdown();
            Close();
        }

        internal void ReleaseBackend(bool backendStopped = false)
        {
            BackendServiceSession session = backendSession;
            backendSession = null;
            if (session == null)
            {
                return;
            }
            try
            {
                if (backendStopped) { session.Dispose(); }
                else { session.Release(updateHandoffVersion == null); }
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
            }
        }

        private void CloseDetachedWindows()
        {
            foreach (Form window in DesktopSession.ReleaseDetachedWindows())
            {
                try
                {
                    if (window != null && !window.IsDisposed)
                    {
                        window.Close();
                        if (!window.IsDisposed && !window.Visible)
                        {
                            window.Dispose();
                        }
                    }
                }
                catch
                {
                }
            }
        }
    }

    internal sealed class SplashView : Control
    {
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer();
        private static readonly DateTime UnixEpoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        private const int ExitDurationMilliseconds = 300;
        private const float ExitRisePixels = 18.0f;
        private const float SpinnerDegreesPerTick = 5.333333f;
        private readonly System.Windows.Forms.Timer timer;
        private readonly Image darkLogo;
        private readonly Image lightLogo;
        private readonly string frontendDirectory;
        private readonly CometSpinnerRaster spinnerRaster;
        private WebView2 webView;
        private bool webReady;
        private float angle;
        private string status;
        private bool failed;
        private bool exiting;
        private bool light;
        private int interfaceScale;
        private long startedAt;
        private float introProgress;
        private float exitProgress;
        private Stopwatch exitStopwatch;
        private TaskCompletionSource<bool> exitCompletion;
        private Rectangle spinnerBounds;

        public SplashView(LauncherPaths paths, bool light, int interfaceScale)
        {
            this.DoubleBuffered = true;
            this.darkLogo = paths.TryLoadLogo(false);
            this.lightLogo = paths.TryLoadLogo(true);
            this.frontendDirectory = paths.FrontendDirectory;
            this.light = light;
            this.interfaceScale = interfaceScale;
            this.BackColor = LauncherAppearance.BackgroundFor(light);
            this.status = "Starting SoAI...";
            this.spinnerRaster = new CometSpinnerRaster();
            this.timer = new System.Windows.Forms.Timer();
            this.timer.Interval = 16;
            this.timer.Tick += delegate
            {
                angle = (angle + SpinnerDegreesPerTick) % 360.0f;
                bool animating = exiting || introProgress < 1.0f;
                if (!failed && !exiting)
                {
                    introProgress = Math.Min(1.0f, introProgress + 0.018f);
                }
                if (exiting)
                {
                    exitProgress = Math.Min(1.0f, (float)exitStopwatch.Elapsed.TotalMilliseconds / ExitDurationMilliseconds);
                }
                if (animating || spinnerBounds.IsEmpty)
                {
                    Invalidate();
                }
                else
                {
                    Invalidate(spinnerBounds);
                }
            };
            this.timer.Start();
        }

        public bool UsesWebView
        {
            get { return webReady; }
        }

        public async Task AttachWebViewAsync(CoreWebView2Environment environment)
        {
            if (webView != null || environment == null || !SplashPage.IsAvailable(frontendDirectory))
            {
                return;
            }

            string page = SplashPage.Build(frontendDirectory);
            WebView2 candidate = new WebView2();
            candidate.DefaultBackgroundColor = LauncherAppearance.BackgroundFor(light);
            candidate.Dock = DockStyle.Fill;
            webView = candidate;
            Controls.Add(candidate);
            try
            {
                await candidate.EnsureCoreWebView2Async(environment);
                CoreWebView2 core = candidate.CoreWebView2;
                core.Settings.AreDevToolsEnabled = false;
                core.Settings.AreDefaultContextMenusEnabled = false;
                core.Settings.AreDefaultScriptDialogsEnabled = false;
                core.Settings.AreBrowserAcceleratorKeysEnabled = false;
                core.Settings.IsStatusBarEnabled = false;
                core.Settings.IsZoomControlEnabled = false;
                core.Settings.IsPinchZoomEnabled = false;
                core.Settings.IsSwipeNavigationEnabled = false;
                core.Settings.IsBuiltInErrorPageEnabled = false;
                core.AddWebResourceRequestedFilter(SplashPage.Origin + "/*", CoreWebView2WebResourceContext.All);
                core.WebResourceRequested += delegate(object sender, CoreWebView2WebResourceRequestedEventArgs e)
                {
                    e.Response = SplashPage.Respond(environment, frontendDirectory, page, e.Request);
                };
                core.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e)
                {
                    if (!string.Equals(e.Uri, SplashPage.PageUri, StringComparison.Ordinal))
                    {
                        e.Cancel = true;
                    }
                };
                core.NewWindowRequested += delegate(object sender, CoreWebView2NewWindowRequestedEventArgs e)
                {
                    e.Handled = true;
                };
                core.ProcessFailed += delegate
                {
                    BeginInvoke(new MethodInvoker(DetachWebView));
                };

                TaskCompletionSource<bool> loaded = new TaskCompletionSource<bool>();
                core.NavigationCompleted += delegate(object sender, CoreWebView2NavigationCompletedEventArgs e)
                {
                    loaded.TrySetResult(e.IsSuccess);
                };
                core.Navigate(SplashPage.PageUri);
                Task finished = await Task.WhenAny(loaded.Task, Task.Delay(TimeSpan.FromSeconds(10)));
                if (finished != loaded.Task || !loaded.Task.Result)
                {
                    throw new InvalidOperationException("The splash page did not load.");
                }
                string styled = await core.ExecuteScriptAsync("!!(window.soaiLauncherSplash&&window.soaiLauncherSplash.isStyled())");
                if (!string.Equals(styled, "true", StringComparison.Ordinal) || webView != candidate)
                {
                    throw new InvalidOperationException("The splash page styles did not load.");
                }
                webReady = true;
                timer.Stop();
                candidate.BringToFront();
                Render();
            }
            catch (Exception)
            {
                DetachWebView();
            }
        }

        public void DetachWebView()
        {
            WebView2 retired = webView;
            if (retired == null)
            {
                return;
            }
            webView = null;
            webReady = false;
            Controls.Remove(retired);
            try
            {
                retired.Dispose();
            }
            catch
            {
            }
            if (!failed)
            {
                timer.Start();
            }
            Invalidate();
        }

        public void Reveal()
        {
            if (startedAt == 0)
            {
                startedAt = CurrentUnixMilliseconds();
            }
            Render();
        }

        public void SetAppearance(bool lightTheme, int scale)
        {
            light = lightTheme;
            interfaceScale = scale;
            BackColor = LauncherAppearance.BackgroundFor(lightTheme);
            if (webView != null)
            {
                webView.DefaultBackgroundColor = BackColor;
            }
            Render();
        }

        public void SetStatus(string value)
        {
            if (failed)
            {
                return;
            }
            status = string.IsNullOrWhiteSpace(value) ? "Starting SoAI..." : value.Trim();
            Render();
        }

        public void ShowFailure(string message)
        {
            ShowFailure("SoAI could not start.", message);
        }

        public void ShowFailure(string heading, string message)
        {
            failed = true;
            timer.Stop();
            status = heading + Environment.NewLine + (message ?? string.Empty).Trim();
            Render();
        }

        public void Restart(string value)
        {
            TaskCompletionSource<bool> pendingExit = exitCompletion;
            if (pendingExit != null && !pendingExit.Task.IsCompleted)
            {
                pendingExit.TrySetCanceled();
            }
            failed = false;
            exiting = false;
            exitProgress = 0.0f;
            exitStopwatch = null;
            exitCompletion = null;
            introProgress = 0.0f;
            status = string.IsNullOrWhiteSpace(value) ? "Starting SoAI..." : value.Trim();
            if (startedAt != 0)
            {
                startedAt = CurrentUnixMilliseconds();
            }
            if (!webReady)
            {
                timer.Start();
            }
            Render();
        }

        public async Task ExitAsync(CancellationToken token)
        {
            if (failed)
            {
                throw new InvalidOperationException("A failed launcher splash cannot exit as a successful startup.");
            }
            if (webReady)
            {
                try
                {
                    if (await TryExitWebViewAsync(token))
                    {
                        return;
                    }
                }
                catch (Exception)
                {
                    token.ThrowIfCancellationRequested();
                }
                DetachWebView();
                introProgress = 1.0f;
            }
            BeginNativeExit();
            TaskCompletionSource<bool> completion = exitCompletion;
            using (token.Register(delegate { completion.TrySetCanceled(); }))
            {
                await completion.Task;
            }
        }

        private async Task<bool> TryExitWebViewAsync(CancellationToken token)
        {
            CoreWebView2 core = webView == null ? null : webView.CoreWebView2;
            if (core == null)
            {
                return false;
            }
            string started = await core.ExecuteScriptAsync("!!(window.soaiLauncherSplash&&window.soaiLauncherSplash.beginExit())");
            if (!string.Equals(started, "true", StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }
            DateTime deadline = DateTime.UtcNow.AddMilliseconds(ExitDurationMilliseconds + 1500);
            while (DateTime.UtcNow < deadline)
            {
                token.ThrowIfCancellationRequested();
                string state = await core.ExecuteScriptAsync("window.soaiLauncherSplash&&window.soaiLauncherSplash.exitState()");
                if (string.Equals(state, "\"completed\"", StringComparison.Ordinal))
                {
                    return true;
                }
                if (string.Equals(state, "\"failed\"", StringComparison.Ordinal))
                {
                    return false;
                }
                await Task.Delay(16, token);
            }
            return false;
        }

        private void BeginNativeExit()
        {
            if (exitCompletion != null)
            {
                return;
            }
            exitCompletion = new TaskCompletionSource<bool>();
            exiting = true;
            exitProgress = 0.0f;
            exitStopwatch = Stopwatch.StartNew();
            timer.Start();
            Invalidate();
        }

        public string BuildBootHandoffScript()
        {
            Dictionary<string, object> handoff = new Dictionary<string, object>();
            handoff["startedAt"] = startedAt;
            handoff["status"] = status;
            return "(function(){'use strict';var handoff=Object.freeze(" + Serializer.Serialize(handoff) + ");" +
                "try{Object.defineProperty(window,'soaiDesktopLauncherBoot',{value:handoff,writable:false,configurable:false});}catch(e){}})();";
        }

        private static long CurrentUnixMilliseconds()
        {
            return (long)(DateTime.UtcNow - UnixEpoch).TotalMilliseconds;
        }

        private void Render()
        {
            if (!webReady || webView == null || webView.CoreWebView2 == null)
            {
                Invalidate();
                return;
            }
            Dictionary<string, object> state = new Dictionary<string, object>();
            state["theme"] = light ? "light" : "dark";
            state["interfaceScale"] = interfaceScale;
            state["startedAt"] = startedAt;
            state["status"] = status;
            state["failed"] = failed;
            try
            {
                webView.CoreWebView2.ExecuteScriptAsync("window.soaiLauncherSplash&&window.soaiLauncherSplash.render(" + Serializer.Serialize(state) + ");");
            }
            catch (Exception)
            {
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            if (webReady)
            {
                return;
            }
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            SplashPalette palette = SplashPalette.For(light);
            PaintBackground(g, palette);

            float px = ResolveDeviceScale(g) * Math.Max(0.5f, interfaceScale / 100.0f);
            float width = ClientSize.Width;
            float height = ClientSize.Height;
            float centerX = width / 2.0f;
            float exitEased = exiting ? EaseOut(exitProgress) : 0.0f;
            float exitOffset = ExitRisePixels * px * exitEased;
            float opacity = 1.0f - exitEased;
            float logoIntro = failed ? 1.0f : EaseOut(Clamp01(introProgress / 0.62f));
            float statusIntro = failed ? 1.0f : EaseOut(Clamp01((introProgress - 0.10f) / 0.72f));
            float spinnerIntro = EaseOut(Clamp01((introProgress - 0.04f) / 0.96f));

            Image logo = light && lightLogo != null ? lightLogo : darkLogo;
            float logoWidth = Math.Min(width * 0.80f, 420.0f * px);
            float logoHeight = Math.Min(logoWidth * 750.0f / 1800.0f, Math.Min(height * 0.30f, 260.0f * px));
            float logoMarginCorrection = logoWidth * 39.0f / 382.0f / 2.4f;
            float gap = 30.0f * px;
            float spinnerSize = Math.Max(40.0f * px, Math.Min(width * 0.15f, 78.0f * px));
            float ring = Math.Max(2.0f * px, spinnerSize * 0.05f);
            float statusWidth = failed ? Math.Min(width * 0.90f, 720.0f * px) : Math.Min(width * 0.78f, 520.0f * px);

            using (Font font = new Font("Segoe UI", 15.2f * px, FontStyle.Regular, GraphicsUnit.Pixel))
            using (StringFormat format = new StringFormat())
            {
                format.Alignment = StringAlignment.Center;
                format.LineAlignment = StringAlignment.Near;
                float lineHeight = 15.2f * px * 1.4f;
                SizeF measured = g.MeasureString(status, font, (int)Math.Ceiling(statusWidth), format);
                int lines = Math.Max(1, (int)Math.Ceiling(measured.Height / Math.Max(1.0f, font.GetHeight(g)) - 0.01f));
                float statusHeight = Math.Min(Math.Max(lineHeight, lines * lineHeight), height * 0.6f);
                float spinnerAreaHeight = failed ? 0.0f : gap + spinnerSize;
                float groupHeight = logoHeight - logoMarginCorrection + gap + statusHeight + spinnerAreaHeight;
                float top = Math.Max(0.0f, (height - groupHeight) / 2.0f);

                if (logo != null)
                {
                    float drawnWidth = Math.Min(logoWidth, logoHeight * logo.Width / Math.Max(1.0f, (float)logo.Height));
                    float drawnHeight = drawnWidth * logo.Height / Math.Max(1.0f, (float)logo.Width);
                    RectangleF logoRect = new RectangleF(
                        centerX - drawnWidth / 2.0f,
                        top + (logoHeight - drawnHeight) / 2.0f - (24.0f * px * (1.0f - logoIntro)) - exitOffset,
                        drawnWidth,
                        drawnHeight);
                    DrawImageWithOpacity(g, logo, logoRect, opacity * logoIntro);
                }

                float statusTop = top + logoHeight - logoMarginCorrection + gap - (12.0f * px * (1.0f - statusIntro)) - exitOffset;
                RectangleF textRect = new RectangleF(centerX - statusWidth / 2.0f, statusTop, statusWidth, statusHeight + lineHeight);
                Color statusColor = failed ? palette.Failure : palette.Status;
                using (Brush brush = new SolidBrush(Color.FromArgb((int)(statusColor.A * opacity * statusIntro), statusColor)))
                {
                    g.DrawString(status, font, brush, textRect, format);
                }

                if (!failed)
                {
                    float spinnerTop = top + logoHeight - logoMarginCorrection + gap + statusHeight + gap - exitOffset;
                    RectangleF box = new RectangleF(centerX - spinnerSize / 2.0f, spinnerTop, spinnerSize, spinnerSize);
                    spinnerBounds = Rectangle.Inflate(Rectangle.Round(box), 2, 2);
                    Image spinnerImage = spinnerRaster.Resolve(spinnerSize, ring, palette);
                    GraphicsState spinnerState = g.Save();
                    try
                    {
                        g.TranslateTransform(box.Left + (box.Width / 2.0f), box.Top + (box.Height / 2.0f));
                        g.RotateTransform(angle);
                        RectangleF spinnerRect = new RectangleF(-box.Width / 2.0f, -box.Height / 2.0f, box.Width, box.Height);
                        DrawImageWithOpacity(g, spinnerImage, spinnerRect, opacity * spinnerIntro);
                    }
                    finally
                    {
                        g.Restore(spinnerState);
                    }
                }
                else
                {
                    spinnerBounds = Rectangle.Empty;
                }
            }
            if (exiting && exitProgress >= 1.0f && exitCompletion != null)
            {
                timer.Stop();
                exitStopwatch.Stop();
                exitCompletion.TrySetResult(true);
            }
        }

        private void PaintBackground(Graphics g, SplashPalette palette)
        {
            Rectangle area = ClientRectangle;
            if (area.Width <= 0 || area.Height <= 0)
            {
                return;
            }
            using (LinearGradientBrush brush = new LinearGradientBrush(area, palette.BackgroundTop, palette.BackgroundBottom, LinearGradientMode.Vertical))
            {
                Blend blend = new Blend(11);
                for (int index = 0; index <= 10; index++)
                {
                    float position = index / 10.0f;
                    blend.Positions[index] = position;
                    blend.Factors[index] = position * position;
                }
                brush.Blend = blend;
                g.FillRectangle(brush, area);
            }
        }

        private float ResolveDeviceScale(Graphics g)
        {
            try
            {
                if (IsHandleCreated)
                {
                    uint dpi = GetDpiForWindow(Handle);
                    if (dpi > 0)
                    {
                        return dpi / 96.0f;
                    }
                }
            }
            catch (EntryPointNotFoundException)
            {
            }
            catch (DllNotFoundException)
            {
            }
            return Math.Max(1.0f, g.DpiX / 96.0f);
        }

        [DllImport("user32.dll")]
        private static extern uint GetDpiForWindow(IntPtr window);

        private static float Clamp01(float value)
        {
            if (value < 0.0f)
            {
                return 0.0f;
            }
            if (value > 1.0f)
            {
                return 1.0f;
            }
            return value;
        }

        private static float EaseOut(float value)
        {
            float t = Clamp01(value);
            return 1.0f - ((1.0f - t) * (1.0f - t));
        }

        private static void DrawImageWithOpacity(Graphics g, Image image, RectangleF rect, float opacity)
        {
            float resolvedOpacity = Math.Max(0.0f, Math.Min(1.0f, opacity));
            PointF[] destination = new PointF[] { new PointF(rect.Left, rect.Top), new PointF(rect.Right, rect.Top), new PointF(rect.Left, rect.Bottom) };
            RectangleF source = new RectangleF(0.0f, 0.0f, image.Width, image.Height);
            if (resolvedOpacity >= 0.999f)
            {
                g.DrawImage(image, destination, source, GraphicsUnit.Pixel);
                return;
            }
            using (System.Drawing.Imaging.ImageAttributes attributes = new System.Drawing.Imaging.ImageAttributes())
            {
                System.Drawing.Imaging.ColorMatrix matrix = new System.Drawing.Imaging.ColorMatrix();
                matrix.Matrix33 = resolvedOpacity;
                attributes.SetColorMatrix(matrix, System.Drawing.Imaging.ColorMatrixFlag.Default, System.Drawing.Imaging.ColorAdjustType.Bitmap);
                g.DrawImage(image, destination, source, GraphicsUnit.Pixel, attributes);
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                if (exitCompletion != null && !exitCompletion.Task.IsCompleted)
                {
                    exitCompletion.TrySetCanceled();
                }
                timer.Dispose();
                spinnerRaster.Dispose();
                if (darkLogo != null)
                {
                    darkLogo.Dispose();
                }
                if (lightLogo != null)
                {
                    lightLogo.Dispose();
                }
            }
            base.Dispose(disposing);
        }
    }

    internal sealed class CometSpinnerRaster : IDisposable
    {
        private const float TrailStartDegrees = 28.0f;
        private const int RasterScale = 4;
        private Bitmap image;
        private int imageSize;
        private float imageRing;
        private int imageTrackColor;
        private int imageActiveColor;

        public Image Resolve(float size, float ring, SplashPalette palette)
        {
            int resolvedSize = Math.Max(1, (int)Math.Ceiling(size * RasterScale));
            float resolvedRing = ring * resolvedSize / Math.Max(1.0f, size);
            int resolvedTrackColor = palette.SpinnerTrack.ToArgb();
            int resolvedActiveColor = palette.Accent.ToArgb();
            if (image != null && imageSize == resolvedSize && Math.Abs(imageRing - resolvedRing) < 0.01f && imageTrackColor == resolvedTrackColor && imageActiveColor == resolvedActiveColor)
            {
                return image;
            }
            Bitmap rendered = Render(resolvedSize, resolvedRing, palette.SpinnerTrack, palette.Accent);
            Bitmap previous = image;
            image = rendered;
            imageSize = resolvedSize;
            imageRing = resolvedRing;
            imageTrackColor = resolvedTrackColor;
            imageActiveColor = resolvedActiveColor;
            if (previous != null)
            {
                previous.Dispose();
            }
            return image;
        }

        private static Bitmap Render(int size, float ring, Color trackColor, Color activeColor)
        {
            Bitmap rendered = new Bitmap(size, size, System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
            try
            {
                int[] pixels = new int[size * size];
                double radius = size / 2.0;
                double innerRadius = Math.Max(0.0, radius - ring);
                double trackAlpha = trackColor.A / 255.0;
                for (int row = 0; row < size; row++)
                {
                    double vertical = row + 0.5 - radius;
                    for (int column = 0; column < size; column++)
                    {
                        double horizontal = column + 0.5 - radius;
                        double distance = Math.Sqrt(horizontal * horizontal + vertical * vertical);
                        double coverage = Math.Max(0.0, Math.Min(1.0, Math.Min(radius - distance + 0.5, distance - innerRadius + 0.5)));
                        if (coverage <= 0.0) continue;
                        double angle = (Math.Atan2(vertical, horizontal) * 180.0 / Math.PI + 450.0) % 360.0;
                        double progress = Math.Max(0.0, (angle - TrailStartDegrees) / (360.0 - TrailStartDegrees));
                        double trailAlpha = activeColor.A / 255.0 * progress * progress;
                        double remainingTrackAlpha = trackAlpha * (1.0 - trailAlpha);
                        int alpha = (int)Math.Round(255.0 * coverage * (trailAlpha + remainingTrackAlpha));
                        int red = (int)Math.Round(coverage * (activeColor.R * trailAlpha + trackColor.R * remainingTrackAlpha));
                        int green = (int)Math.Round(coverage * (activeColor.G * trailAlpha + trackColor.G * remainingTrackAlpha));
                        int blue = (int)Math.Round(coverage * (activeColor.B * trailAlpha + trackColor.B * remainingTrackAlpha));
                        pixels[row * size + column] = (alpha << 24) | (red << 16) | (green << 8) | blue;
                    }
                }
                System.Drawing.Imaging.BitmapData bitmapData = rendered.LockBits(new Rectangle(0, 0, size, size), System.Drawing.Imaging.ImageLockMode.WriteOnly, System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
                try
                {
                    Marshal.Copy(pixels, 0, bitmapData.Scan0, pixels.Length);
                }
                finally
                {
                    rendered.UnlockBits(bitmapData);
                }
            }
            catch
            {
                rendered.Dispose();
                throw;
            }
            return rendered;
        }

        public void Dispose()
        {
            if (image != null)
            {
                image.Dispose();
                image = null;
            }
        }
    }

    internal sealed class SplashPalette
    {
        public Color BackgroundTop;
        public Color BackgroundBottom;
        public Color Status;
        public Color Failure;
        public Color SpinnerTrack;
        public Color Accent;

        public static SplashPalette For(bool light)
        {
            SplashPalette palette = new SplashPalette();
            if (light)
            {
                palette.BackgroundTop = Color.FromArgb(217, 217, 217);
                palette.BackgroundBottom = Color.FromArgb(173, 173, 173);
                palette.Status = Color.FromArgb(174, 15, 15, 17);
                palette.Failure = Color.FromArgb(255, 160, 40, 40);
                palette.SpinnerTrack = Color.FromArgb(38, 15, 15, 17);
                palette.Accent = Color.FromArgb(102, 130, 18);
            }
            else
            {
                palette.BackgroundTop = Color.FromArgb(36, 38, 36);
                palette.BackgroundBottom = Color.FromArgb(23, 25, 23);
                palette.Status = Color.FromArgb(174, 230, 230, 230);
                palette.Failure = Color.FromArgb(255, 225, 140, 140);
                palette.SpinnerTrack = Color.FromArgb(38, 230, 230, 230);
                palette.Accent = Color.FromArgb(134, 179, 30);
            }
            return palette;
        }
    }

    internal static class SplashPage
    {
        public const string Origin = "https://soai-launcher.invalid";
        public const string PageUri = Origin + "/splash.html";
        private const string MainStylesheetPlaceholder = "@MAIN_STYLESHEET@";

        private const string Template = @"<!doctype html>
<html lang=""en"" data-soai-boot-state=""booting"" data-animation-speed=""normal"" data-interface-scale=""100"" class=""theme-dark"" style=""color-scheme: dark"">
    <head>
        <meta charset=""UTF-8"" />
        <meta name=""viewport"" content=""width=device-width, initial-scale=1.0"" />
        <title>SoAI</title>
        <link rel=""stylesheet"" href=""./assets/css/boot.css"" />
        @MAIN_STYLESHEET@
        <style>
            html[data-soai-boot-state]:not(.launcher-splash-started):not(.launcher-splash-failed) .page-preloader-content {
                visibility: hidden;
            }

            html[data-soai-boot-state] .page-preloader-status {
                white-space: pre-line;
                overflow-wrap: anywhere;
            }

            html[data-soai-boot-state].preloader-status-ready .page-preloader-status {
                max-height: max(1.4rem, var(--launcher-status-block-size, 0px));
            }

            html.launcher-splash-failed .page-preloader-status {
                max-width: min(calc(90 * var(--ui-viewport-width-unit)), 720px);
                color: var(--launcher-failure-color);
                user-select: text;
            }

            html.launcher-splash-failed .page-preloader-spinner {
                display: none;
            }

            :root.theme-dark {
                --launcher-failure-color: rgb(225 140 140);
            }

            :root.theme-light {
                --launcher-failure-color: rgb(160 40 40);
            }
        </style>
    </head>
    <body class=""ui-ready ui-animated sidebar-collapsed"">
        <div id=""page-preloader"" class=""page-preloader"" aria-hidden=""false"">
            <div class=""page-preloader-content"">
                <img class=""page-preloader-logo"" alt=""SoAI"" data-logo-type=""ui"" />
                <div class=""page-preloader-status"" role=""status"" aria-live=""polite""></div>
                <div class=""page-preloader-spinner""></div>
                <div class=""page-preloader-text"" role=""status"" aria-live=""polite""></div>
            </div>
        </div>
        <script>
            (function () {
                'use strict';
                var REVEAL_DELAY_MS = 3000;
                var STATUS_AFTER_LOGO_MS = 6000;
                var root = document.documentElement;
                var preloader = document.getElementById('page-preloader');
                var content = document.querySelector('.page-preloader-content');
                var logo = document.querySelector('.page-preloader-logo');
                var status = document.querySelector('.page-preloader-status');
                var spinner = document.querySelector('.page-preloader-spinner');
                var theme = 'dark';
                var startedAt = 0;
                var sequence = 0;
                var currentExitState = 'idle';

                var logoPath = function (name) {
                    return './assets/img/soai/soai-logo-' + name + '.png';
                };
                var wait = function (duration) {
                    return new Promise(function (resolve) {
                        setTimeout(resolve, Math.max(0, duration));
                    });
                };
                var preload = function (source) {
                    return new Promise(function (resolve, reject) {
                        var image = new Image();
                        image.decoding = 'async';
                        image.onload = function () {
                            image.decode().then(function () {
                                resolve(image);
                            }, reject);
                        };
                        image.onerror = reject;
                        image.src = source;
                    });
                };
                var align = function (elements, origin, subtree) {
                    var elapsed = Math.max(0, Date.now() - origin);
                    elements.forEach(function (element) {
                        element.getAnimations({ subtree: subtree === true }).forEach(function (animation) {
                            animation.currentTime = elapsed;
                        });
                    });
                };
                var applyTheme = function (next) {
                    if (next === theme) {
                        return;
                    }
                    theme = next;
                    root.classList.remove('theme-dark', 'theme-light');
                    root.classList.add('theme-' + next);
                    root.style.setProperty('color-scheme', next);
                    if (logo.getAttribute('src')) {
                        logo.src = logoPath(next);
                    }
                };
                var run = function (token) {
                    var logoAt = startedAt + REVEAL_DELAY_MS;
                    var statusAt = logoAt + STATUS_AFTER_LOGO_MS;
                    return Promise.all([preload(logoPath(theme)), wait(logoAt - Date.now())])
                        .then(function (loaded) {
                            if (token !== sequence) {
                                return null;
                            }
                            logo.src = loaded[0].src;
                            requestAnimationFrame(function () {
                                requestAnimationFrame(function () {
                                    if (token !== sequence) {
                                        return;
                                    }
                                    root.classList.add('preloader-logo-ready');
                                    align([content, logo], logoAt);
                                });
                            });
                            return wait(statusAt - Date.now());
                        })
                        .then(function () {
                            if (token !== sequence) {
                                return;
                            }
                            root.classList.add('preloader-status-ready');
                            align([status], statusAt);
                        });
                };
                var measureStatus = function () {
                    var range = document.createRange();
                    var tops = [];
                    range.selectNodeContents(status);
                    Array.prototype.forEach.call(range.getClientRects(), function (rect) {
                        var top = Math.round(rect.top);
                        if (tops.indexOf(top) < 0) {
                            tops.push(top);
                        }
                    });
                    var lineHeight = parseFloat(getComputedStyle(status).lineHeight) || 0;
                    root.style.setProperty('--launcher-status-block-size', Math.ceil(Math.max(1, tops.length) * lineHeight) + 'px');
                };
                window.addEventListener('resize', measureStatus);
                var resetExit = function () {
                    currentExitState = 'idle';
                    preloader.classList.remove('page-preloader--exiting');
                    preloader.setAttribute('aria-hidden', 'false');
                };
                var beginExit = function () {
                    if (currentExitState === 'pending' || currentExitState === 'completed') {
                        return true;
                    }
                    currentExitState = 'pending';
                    preloader.classList.add('page-preloader--exiting');
                    preloader.setAttribute('aria-hidden', 'true');
                    requestAnimationFrame(function () {
                        var exits = preloader.getAnimations().filter(function (animation) {
                            return animation.animationName === 'preloader-exit';
                        });
                        if (exits.length !== 1) {
                            currentExitState = 'failed';
                            return;
                        }
                        exits[0].finished.then(function () {
                            currentExitState = 'completed';
                        }, function () {
                            currentExitState = 'failed';
                        });
                    });
                    return true;
                };
                var render = function (state) {
                    applyTheme(state.theme === 'light' ? 'light' : 'dark');
                    root.setAttribute('data-interface-scale', String(state.interfaceScale));
                    root.classList.toggle('launcher-splash-failed', state.failed === true);
                    status.textContent = state.status;
                    measureStatus();
                    if (state.failed === true) {
                        sequence += 1;
                        logo.src = logoPath(theme);
                        root.classList.add('preloader-logo-ready', 'preloader-status-ready');
                        return;
                    }
                    if (!(state.startedAt > 0) || state.startedAt === startedAt) {
                        return;
                    }
                    startedAt = state.startedAt;
                    sequence += 1;
                    resetExit();
                    root.classList.remove('preloader-logo-ready', 'preloader-status-ready');
                    logo.removeAttribute('src');
                    root.classList.add('launcher-splash-started');
                    align([spinner], startedAt, true);
                    run(sequence).catch(function () {});
                };
                window.soaiLauncherSplash = Object.freeze({
                    render: render,
                    beginExit: beginExit,
                    exitState: function () {
                        return currentExitState;
                    },
                    isStyled: function () {
                        return getComputedStyle(root).getPropertyValue('--boot-spinner-size').trim() !== '';
                    }
                });
            })();
        </script>
    </body>
</html>
";

        public static bool IsAvailable(string frontendDirectory)
        {
            return !string.IsNullOrWhiteSpace(frontendDirectory)
                && File.Exists(Path.Combine(frontendDirectory, "assets", "css", "boot.css"));
        }

        public static string Build(string frontendDirectory)
        {
            string mainStylesheet = FindMainStylesheet(frontendDirectory);
            return Template.Replace(
                MainStylesheetPlaceholder,
                mainStylesheet == null ? string.Empty : "<link rel=\"stylesheet\" href=\"./" + mainStylesheet + "\" />");
        }

        private static string FindMainStylesheet(string frontendDirectory)
        {
            try
            {
                string index = File.ReadAllText(Path.Combine(frontendDirectory, "index.html"));
                Match match = Regex.Match(index, "href=\"\\./(assets/build/css/main-[A-Za-z0-9_-]+\\.css)\"");
                return match.Success ? match.Groups[1].Value : null;
            }
            catch (IOException)
            {
                return null;
            }
            catch (UnauthorizedAccessException)
            {
                return null;
            }
        }

        public static CoreWebView2WebResourceResponse Respond(
            CoreWebView2Environment environment,
            string frontendDirectory,
            string page,
            CoreWebView2WebResourceRequest request)
        {
            Uri uri;
            if (!string.Equals(request.Method, "GET", StringComparison.OrdinalIgnoreCase)
                || !Uri.TryCreate(request.Uri, UriKind.Absolute, out uri)
                || !string.Equals(uri.GetLeftPart(UriPartial.Authority), Origin, StringComparison.OrdinalIgnoreCase))
            {
                return NotFound(environment);
            }

            string path = Uri.UnescapeDataString(uri.AbsolutePath);
            if (string.Equals(path, "/splash.html", StringComparison.Ordinal))
            {
                return Create(environment, Encoding.UTF8.GetBytes(page), "text/html; charset=utf-8");
            }

            string contentType = ResolveContentType(path);
            if (contentType == null || !path.StartsWith("/assets/", StringComparison.Ordinal))
            {
                return NotFound(environment);
            }
            try
            {
                string root = Path.GetFullPath(frontendDirectory).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                string file = Path.GetFullPath(Path.Combine(root, path.Substring(1).Replace('/', Path.DirectorySeparatorChar)));
                if (!file.StartsWith(root, StringComparison.OrdinalIgnoreCase) || !File.Exists(file))
                {
                    return NotFound(environment);
                }
                return Create(environment, File.ReadAllBytes(file), contentType);
            }
            catch (Exception)
            {
                return NotFound(environment);
            }
        }

        private static string ResolveContentType(string path)
        {
            string extension = Path.GetExtension(path).ToLowerInvariant();
            switch (extension)
            {
                case ".css":
                    return "text/css; charset=utf-8";
                case ".png":
                    return "image/png";
                case ".svg":
                    return "image/svg+xml";
                case ".webp":
                    return "image/webp";
                case ".jpg":
                case ".jpeg":
                    return "image/jpeg";
                case ".woff2":
                    return "font/woff2";
                default:
                    return null;
            }
        }

        private static CoreWebView2WebResourceResponse Create(CoreWebView2Environment environment, byte[] content, string contentType)
        {
            return environment.CreateWebResourceResponse(
                new MemoryStream(content),
                200,
                "OK",
                "Content-Type: " + contentType + "\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff");
        }

        private static CoreWebView2WebResourceResponse NotFound(CoreWebView2Environment environment)
        {
            return environment.CreateWebResourceResponse(null, 404, "Not Found", "Cache-Control: no-store");
        }
    }

    internal sealed class LauncherAppearance
    {
        private const string FileName = "launcher-appearance.txt";
        private const int DwmUseImmersiveDarkMode = 20;
        private const int DwmUseImmersiveDarkModeBefore20H1 = 19;
        private const int DwmBorderColor = 34;
        private const int DwmCaptionColor = 35;
        private const int DwmTextColor = 36;
        private const uint SwpNoSize = 0x0001;
        private const uint SwpNoMove = 0x0002;
        private const uint SwpNoZOrder = 0x0004;
        private const uint SwpNoActivate = 0x0010;
        private const uint SwpFrameChanged = 0x0020;

        private LauncherAppearance(string preference, int interfaceScale)
        {
            Preference = preference;
            InterfaceScale = interfaceScale;
        }

        public string Preference { get; private set; }
        public int InterfaceScale { get; private set; }

        public bool IsLight
        {
            get
            {
                return string.Equals(Preference, "light", StringComparison.Ordinal)
                    || (string.Equals(Preference, "auto", StringComparison.Ordinal) && SystemUsesLightTheme());
            }
        }

        public static LauncherAppearance Create(string preference, int interfaceScale)
        {
            bool validPreference = string.Equals(preference, "light", StringComparison.Ordinal)
                || string.Equals(preference, "dark", StringComparison.Ordinal)
                || string.Equals(preference, "auto", StringComparison.Ordinal);
            bool validScale = interfaceScale == 50 || interfaceScale == 75 || interfaceScale == 100 || interfaceScale == 125 || interfaceScale == 150;
            return validPreference && validScale ? new LauncherAppearance(preference, interfaceScale) : null;
        }

        public static LauncherAppearance Load(string stateDirectory)
        {
            string preference = "dark";
            int interfaceScale = 100;
            try
            {
                string path = Path.Combine(stateDirectory, FileName);
                if (File.Exists(path))
                {
                    foreach (string line in File.ReadAllLines(path))
                    {
                        int separator = line.IndexOf('=');
                        if (separator <= 0)
                        {
                            continue;
                        }
                        string key = line.Substring(0, separator).Trim();
                        string value = line.Substring(separator + 1).Trim();
                        int scale;
                        if (key == "preference")
                        {
                            preference = value;
                        }
                        else if (key == "interfaceScale" && int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out scale))
                        {
                            interfaceScale = scale;
                        }
                    }
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
            catch (ArgumentException)
            {
            }
            return Create(preference, interfaceScale) ?? new LauncherAppearance("dark", 100);
        }

        public bool SameAs(LauncherAppearance other)
        {
            return other != null
                && string.Equals(Preference, other.Preference, StringComparison.Ordinal)
                && InterfaceScale == other.InterfaceScale;
        }

        public void Save(string stateDirectory)
        {
            try
            {
                Directory.CreateDirectory(stateDirectory);
                File.WriteAllText(
                    Path.Combine(stateDirectory, FileName),
                    "preference=" + Preference + "\ninterfaceScale=" + InterfaceScale.ToString(CultureInfo.InvariantCulture) + "\n");
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }

        public static Color BackgroundFor(bool light)
        {
            return light ? Color.FromArgb(222, 222, 222) : Color.FromArgb(21, 21, 21);
        }

        public static bool SystemUsesLightTheme()
        {
            try
            {
                object value = Registry.GetValue(
                    "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
                    "AppsUseLightTheme",
                    null);
                return !(value is int) || (int)value != 0;
            }
            catch (Exception)
            {
                return true;
            }
        }

        public static Color CaptionColorFor(bool light)
        {
            return light ? Color.FromArgb(217, 217, 217) : Color.FromArgb(36, 38, 36);
        }

        public static Color CaptionTextColorFor(bool light)
        {
            return light ? Color.FromArgb(15, 15, 17) : Color.FromArgb(230, 230, 230);
        }

        private static int ToColorRef(Color color)
        {
            return color.R | (color.G << 8) | (color.B << 16);
        }

        public static void ApplyToWindow(Form form, bool light)
        {
            if (form == null || form.IsDisposed)
            {
                return;
            }
            form.BackColor = BackgroundFor(light);
            if (!form.IsHandleCreated)
            {
                return;
            }
            int dark = light ? 0 : 1;
            try
            {
                if (DwmSetWindowAttribute(form.Handle, DwmUseImmersiveDarkMode, ref dark, Marshal.SizeOf(typeof(int))) != 0)
                {
                    DwmSetWindowAttribute(form.Handle, DwmUseImmersiveDarkModeBefore20H1, ref dark, Marshal.SizeOf(typeof(int)));
                }
                int caption = ToColorRef(CaptionColorFor(light));
                int text = ToColorRef(CaptionTextColorFor(light));
                DwmSetWindowAttribute(form.Handle, DwmCaptionColor, ref caption, Marshal.SizeOf(typeof(int)));
                DwmSetWindowAttribute(form.Handle, DwmBorderColor, ref caption, Marshal.SizeOf(typeof(int)));
                DwmSetWindowAttribute(form.Handle, DwmTextColor, ref text, Marshal.SizeOf(typeof(int)));
                if (form.Visible)
                {
                    SetWindowPos(form.Handle, IntPtr.Zero, 0, 0, 0, 0, SwpNoSize | SwpNoMove | SwpNoZOrder | SwpNoActivate | SwpFrameChanged);
                }
            }
            catch (DllNotFoundException)
            {
            }
            catch (EntryPointNotFoundException)
            {
            }
        }

        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr window, int attribute, ref int attributeValue, int attributeSize);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetWindowPos(IntPtr window, IntPtr insertAfter, int x, int y, int width, int height, uint flags);
    }

    internal static class UpdateProgressWindow
    {
        private const string HostDirectoryName = "update-progress";
        private const string Argument = "--soai-update-progress";
        private static readonly string[] HostFiles = new string[]
        {
            "soai.exe",
            "soai.exe.config",
            "Microsoft.Web.WebView2.Core.dll",
            "Microsoft.Web.WebView2.WinForms.dll",
            "soai-app.ico"
        };
        private static readonly string[] HostLogos = new string[] { "soai-logo-dark.png", "soai-logo-light.png" };

        public static bool IsCommand(string[] args)
        {
            return args != null && args.Length == 3 && string.Equals(args[0], Argument, StringComparison.Ordinal);
        }

        public static int Run(string[] args)
        {
            string installRoot = Path.GetFullPath(args[1]);
            if (!File.Exists(Path.Combine(installRoot, "soai.exe")) || !ReleaseVersionText.IsValid(args[2]))
            {
                return 2;
            }
            LoopbackCertificatePolicy.Install();
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (UpdateProgressForm form = new UpdateProgressForm(installRoot, args[2]))
            {
                Application.Run(form);
            }
            return 0;
        }

        public static bool TryStart(LauncherPaths paths, string targetVersion)
        {
            try
            {
                string hostRoot = Path.Combine(LauncherPaths.UserStateDirectory, HostDirectoryName);
                RemoveIdleHosts(hostRoot);
                string host = Path.Combine(hostRoot, Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(host);
                foreach (string name in HostFiles)
                {
                    File.Copy(Path.Combine(paths.RootDirectory, name), Path.Combine(host, name), false);
                }
                foreach (string name in HostLogos)
                {
                    File.Copy(Path.Combine(paths.FrontendDirectory, "assets", "img", "soai", name), Path.Combine(host, name), false);
                }
                ProcessStartInfo startInfo = new ProcessStartInfo();
                startInfo.FileName = Path.Combine(host, "soai.exe");
                startInfo.Arguments = BackendProcess.BuildArgumentString(new string[] { Argument, paths.RootDirectory, targetVersion }).TrimStart();
                startInfo.WorkingDirectory = host;
                startInfo.UseShellExecute = false;
                using (Process.Start(startInfo))
                {
                }
                return true;
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                return false;
            }
        }

        private static void RemoveIdleHosts(string hostRoot)
        {
            if (!Directory.Exists(hostRoot))
            {
                return;
            }
            foreach (string host in Directory.GetDirectories(hostRoot))
            {
                try
                {
                    Directory.Delete(host, true);
                }
                catch (IOException)
                {
                }
                catch (UnauthorizedAccessException)
                {
                }
            }
        }
    }

    internal sealed class UpdateProgressForm : Form
    {
        private static readonly TimeSpan MaximumLifetime = TimeSpan.FromHours(3);
        private static readonly TimeSpan ReopenGracePeriod = TimeSpan.FromMinutes(2);
        private const string ReopenNotice = "SoAI will reopen automatically when it is ready.";
        private const string DurationNotice = "This can take several minutes. Don't turn off your computer.";

        private readonly string installRoot;
        private readonly string launcherPath;
        private readonly string targetVersion;
        private readonly SplashView splash;
        private readonly System.Windows.Forms.Timer poll;
        private readonly DateTime deadlineUtc;
        private DateTime? reopenedAtUtc;
        private bool refreshing;

        public UpdateProgressForm(string installRoot, string targetVersion)
        {
            this.installRoot = installRoot;
            this.launcherPath = Path.Combine(installRoot, "soai.exe");
            this.targetVersion = targetVersion;
            this.deadlineUtc = DateTime.UtcNow + MaximumLifetime;
            LauncherPaths assets = LauncherPaths.ForAssetDirectory(AppDomain.CurrentDomain.BaseDirectory);
            LauncherAppearance appearance = LauncherAppearance.Load(LauncherPaths.UserStateDirectory);
            bool light = appearance.IsLight;

            Text = "SoAI update";
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Dpi;
            Size = new Size(760, 540);
            MinimumSize = Size;
            MaximizeBox = false;
            BackColor = LauncherAppearance.BackgroundFor(light);
            Icon = assets.TryLoadIcon();
            HandleCreated += delegate { LauncherAppearance.ApplyToWindow(this, light); };

            splash = new SplashView(assets, light, appearance.InterfaceScale);
            splash.Dock = DockStyle.Fill;
            Controls.Add(splash);
            splash.SendToBack();
            splash.SetStatus(DescribeProgress(TransactionIsPending()));

            poll = new System.Windows.Forms.Timer();
            poll.Interval = 1000;
            poll.Tick += async delegate { await RefreshProgressAsync(); };
            Shown += delegate
            {
                splash.Reveal();
                poll.Start();
            };
        }

        private async Task RefreshProgressAsync()
        {
            if (refreshing || IsDisposed)
            {
                return;
            }
            refreshing = true;
            try
            {
                DateTime now = DateTime.UtcNow;
                if (now >= deadlineUtc
                    || (reopenedAtUtc.HasValue && (LauncherWindowIsVisible() || now - reopenedAtUtc.Value >= ReopenGracePeriod)))
                {
                    poll.Stop();
                    Close();
                    return;
                }
                if (reopenedAtUtc.HasValue)
                {
                    return;
                }
                bool pending = TransactionIsPending();
                splash.SetStatus(DescribeProgress(pending));
                if (pending)
                {
                    return;
                }
                EndpointInfo endpoint = await DiscoveryProbe.TryResolveAsync(CancellationToken.None);
                if (endpoint == null || !await HealthProbe.IsReadyAsync(endpoint, CancellationToken.None) || IsDisposed)
                {
                    return;
                }
                reopenedAtUtc = DateTime.UtcNow;
                if (LauncherWindowIsVisible())
                {
                    return;
                }
                ProcessStartInfo startInfo = new ProcessStartInfo();
                startInfo.FileName = launcherPath;
                startInfo.Arguments = LauncherCommand.AfterUpdateArgument;
                startInfo.WorkingDirectory = installRoot;
                startInfo.UseShellExecute = false;
                using (Process.Start(startInfo))
                {
                }
            }
            catch (Exception exception)
            {
                poll.Stop();
                splash.ShowFailure("SoAI could not reopen after the update.", "Start SoAI from its shortcut. Details: " + exception.Message);
            }
            finally
            {
                refreshing = false;
            }
        }

        private string DescribeProgress(bool pending)
        {
            if (!pending)
            {
                return "Opening SoAI " + targetVersion + "..." + Environment.NewLine + ReopenNotice;
            }
            return "Installing SoAI " + targetVersion + "..." + Environment.NewLine + ReopenNotice + Environment.NewLine + DurationNotice;
        }

        private bool TransactionIsPending()
        {
            try
            {
                return Directory.GetDirectories(installRoot, ".soai_update_transaction_*").Length > 0;
            }
            catch (IOException)
            {
                return false;
            }
            catch (UnauthorizedAccessException)
            {
                return false;
            }
        }

        private bool LauncherWindowIsVisible()
        {
            int currentProcessId;
            using (Process current = Process.GetCurrentProcess())
            {
                currentProcessId = current.Id;
            }
            foreach (Process candidate in Process.GetProcessesByName("soai"))
            {
                using (candidate)
                {
                    try
                    {
                        IntPtr window = candidate.MainWindowHandle;
                        if (candidate.Id == currentProcessId || window == IntPtr.Zero || !IsWindowVisible(window))
                        {
                            continue;
                        }
                        if (string.Equals(QueryImagePath(candidate.Id), launcherPath, StringComparison.OrdinalIgnoreCase))
                        {
                            return true;
                        }
                    }
                    catch (InvalidOperationException)
                    {
                    }
                }
            }
            return false;
        }

        private static string QueryImagePath(int processId)
        {
            IntPtr process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, processId);
            if (process == IntPtr.Zero)
            {
                return null;
            }
            try
            {
                StringBuilder path = new StringBuilder(32768);
                int length = path.Capacity;
                return QueryFullProcessImageName(process, 0, path, ref length) ? path.ToString(0, length) : null;
            }
            finally
            {
                CloseHandle(process);
            }
        }

        private const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x00001000;

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool IsWindowVisible(IntPtr window);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint desiredAccess, bool inheritHandle, int processId);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool QueryFullProcessImageName(IntPtr process, int flags, StringBuilder path, ref int length);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr handle);

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                poll.Dispose();
            }
            base.Dispose(disposing);
        }
    }

    internal sealed class DetachedWebViewForm : Form
    {
        private bool hiddenUntilContent;

        private bool lightTheme;

        public DetachedWebViewForm(Icon icon, bool light)
        {
            lightTheme = light;
            Text = "SoAI";
            StartPosition = FormStartPosition.CenterScreen;
            MinimumSize = new Size(860, 620);
            Size = new Size(1120, 760);
            BackColor = LauncherAppearance.BackgroundFor(light);
            try
            {
                if (icon != null)
                {
                    Icon = (Icon)icon.Clone();
                }
            }
            catch
            {
            }

            WebView = new WebView2();
            WebView.Dock = DockStyle.Fill;
            WebView.DefaultBackgroundColor = LauncherAppearance.BackgroundFor(light);
            Controls.Add(WebView);
            HandleCreated += delegate { LauncherAppearance.ApplyToWindow(this, lightTheme); };
        }

        public WebView2 WebView { get; private set; }

        public bool HiddenUntilContent
        {
            get { return hiddenUntilContent; }
        }

        public async Task InitializeAsync(CoreWebView2Environment environment)
        {
            await WebView.EnsureCoreWebView2Async(environment);
        }

        public void ShowHidden()
        {
            hiddenUntilContent = true;
            Opacity = 0.0;
            ShowInTaskbar = false;
            Show();
        }

        public void Reveal()
        {
            if (!hiddenUntilContent || IsDisposed)
            {
                return;
            }
            hiddenUntilContent = false;
            Opacity = 1.0;
            ShowInTaskbar = true;
            WindowState = FormWindowState.Normal;
            Show();
            Activate();
        }

        public void ApplyTheme(bool light)
        {
            if (IsDisposed)
            {
                return;
            }
            lightTheme = light;
            LauncherAppearance.ApplyToWindow(this, light);
            WebView.DefaultBackgroundColor = LauncherAppearance.BackgroundFor(light);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            FullScreenMode.Set(this, false);
            base.OnFormClosing(e);
        }
    }

    internal static class HostWebMessages
    {
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer();

        public static bool TryRead(
            CoreWebView2WebMessageReceivedEventArgs eventArgs,
            Func<string, bool> isTrustedSource,
            string channel,
            out Dictionary<string, object> message,
            out string command)
        {
            message = null;
            command = null;
            if (eventArgs == null || !isTrustedSource(eventArgs.Source))
            {
                return false;
            }
            try
            {
                message = Serializer.Deserialize<Dictionary<string, object>>(eventArgs.TryGetWebMessageAsString());
            }
            catch
            {
                message = null;
                return false;
            }
            object channelValue;
            object commandValue;
            if (message == null
                || !message.TryGetValue("channel", out channelValue)
                || !message.TryGetValue("command", out commandValue)
                || !string.Equals(channelValue as string, channel, StringComparison.Ordinal)
                || !(commandValue is string))
            {
                message = null;
                return false;
            }
            command = (string)commandValue;
            return true;
        }
    }

    public static class ReleaseVersionText
    {
        private const int MaxLength = 64;
        private static readonly Regex Pattern = new Regex(
            "\\A[0-9]+\\.[0-9]+\\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?\\z",
            RegexOptions.CultureInvariant);

        public static bool IsValid(string value)
        {
            return value != null && value.Length <= MaxLength && Pattern.IsMatch(value);
        }
    }

    internal static class DesktopLauncherBridge
    {
        private const string Channel = "soai.desktopLauncher.v1";
        internal const string CapabilityScript = "(function(){'use strict';var capability=Object.freeze({platform:'windows',protocolVersion:1});" +
            "try{Object.defineProperty(window,'soaiDesktopLauncher',{value:capability,writable:false,configurable:false});}" +
            "catch(e){window.soaiDesktopLauncher=capability;}})();";

        public static async Task AttachAsync(
            CoreWebView2 core,
            Func<string, bool> isTrustedSource,
            Action<string> onUpdateHandoff,
            Action onBootReveal,
            Action<LauncherAppearance, bool> onAppearance)
        {
            await core.AddScriptToExecuteOnDocumentCreatedAsync(CapabilityScript);
            core.WebMessageReceived += delegate(object sender, CoreWebView2WebMessageReceivedEventArgs e)
            {
                Dictionary<string, object> message;
                string command;
                if (!HostWebMessages.TryRead(e, isTrustedSource, Channel, out message, out command))
                {
                    return;
                }
                if (string.Equals(command, "updateHandoff", StringComparison.Ordinal))
                {
                    object versionValue;
                    string version = message.TryGetValue("targetVersion", out versionValue) ? versionValue as string : null;
                    if (message.Count != 3 || !ReleaseVersionText.IsValid(version))
                    {
                        return;
                    }
                    onUpdateHandoff(version);
                }
                else if (string.Equals(command, "bootReveal", StringComparison.Ordinal) && message.Count == 2)
                {
                    onBootReveal();
                }
                else if (string.Equals(command, "appearance", StringComparison.Ordinal) && message.Count == 5)
                {
                    object preference;
                    object theme;
                    object interfaceScale;
                    message.TryGetValue("preference", out preference);
                    message.TryGetValue("theme", out theme);
                    message.TryGetValue("interfaceScale", out interfaceScale);
                    LauncherAppearance appearance = LauncherAppearance.Create(preference as string, interfaceScale is int ? (int)interfaceScale : 0);
                    string resolvedTheme = theme as string;
                    if (appearance == null || (resolvedTheme != "light" && resolvedTheme != "dark"))
                    {
                        return;
                    }
                    onAppearance(appearance, resolvedTheme == "light");
                }
            };
        }
    }

    internal static class FullScreenMode
    {
        private sealed class Snapshot
        {
            public FormBorderStyle BorderStyle;
            public FormWindowState WindowState;
            public Rectangle Bounds;
            public bool TopMost;
        }

        private static readonly Dictionary<Form, Snapshot> Snapshots = new Dictionary<Form, Snapshot>();

        public static void Set(Form form, bool fullScreen)
        {
            if (form == null || form.IsDisposed)
            {
                return;
            }

            if (fullScreen)
            {
                if (Snapshots.ContainsKey(form))
                {
                    return;
                }
                Snapshots[form] = new Snapshot
                {
                    BorderStyle = form.FormBorderStyle,
                    WindowState = form.WindowState,
                    Bounds = form.Bounds,
                    TopMost = form.TopMost
                };
                Rectangle bounds = Screen.FromControl(form).Bounds;
                form.SuspendLayout();
                form.WindowState = FormWindowState.Normal;
                form.FormBorderStyle = FormBorderStyle.None;
                form.Bounds = bounds;
                form.TopMost = true;
                form.ResumeLayout();
                return;
            }

            Snapshot snapshot;
            if (!Snapshots.TryGetValue(form, out snapshot))
            {
                return;
            }
            Snapshots.Remove(form);
            form.SuspendLayout();
            form.TopMost = snapshot.TopMost;
            form.FormBorderStyle = snapshot.BorderStyle;
            form.Bounds = snapshot.Bounds;
            form.WindowState = snapshot.WindowState;
            form.ResumeLayout();
        }
    }

    internal static class TrustedWebContent
    {
        public static bool IsBlankWindowUri(string value)
        {
            string text = (value ?? string.Empty).Trim();
            return text.Length == 0 || string.Equals(text, "about:blank", StringComparison.OrdinalIgnoreCase);
        }

        public static bool IsTrustedAppUri(string value)
        {
            Uri uri;
            if (!Uri.TryCreate(value, UriKind.Absolute, out uri))
            {
                return false;
            }

            return (string.Equals(uri.Scheme, "http", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(uri.Scheme, "https", StringComparison.OrdinalIgnoreCase))
                && LoopbackCertificatePolicy.IsLoopbackUri(uri.AbsoluteUri);
        }

        public static bool IsWebViewGeneratedContentUri(string value)
        {
            Uri uri;
            if (!Uri.TryCreate(value, UriKind.Absolute, out uri))
            {
                return false;
            }

            return string.Equals(uri.Scheme, "blob", StringComparison.OrdinalIgnoreCase)
                || string.Equals(uri.Scheme, "data", StringComparison.OrdinalIgnoreCase);
        }

        public static bool TryOpenExternalUri(string value, bool userInitiated)
        {
            if (!userInitiated)
            {
                return false;
            }

            Uri uri;
            if (!Uri.TryCreate(value, UriKind.Absolute, out uri))
            {
                return false;
            }
            if (!string.Equals(uri.Scheme, "http", StringComparison.OrdinalIgnoreCase)
                && !string.Equals(uri.Scheme, "https", StringComparison.OrdinalIgnoreCase)
                && !string.Equals(uri.Scheme, "mailto", StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = uri.AbsoluteUri;
                psi.UseShellExecute = true;
                Process.Start(psi);
                return true;
            }
            catch
            {
                return false;
            }
        }
    }

    internal static class DownloadTargets
    {
        public static string ResolveDownloadDirectory()
        {
            string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            if (string.IsNullOrWhiteSpace(userProfile))
            {
                userProfile = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            }
            if (string.IsNullOrWhiteSpace(userProfile))
            {
                userProfile = Path.GetTempPath();
            }
            return Path.Combine(userProfile, "Downloads");
        }

        public static string ResolveFileName(CoreWebView2DownloadStartingEventArgs e)
        {
            string fileName = FileNameFromPath(e.ResultFilePath);
            if (string.IsNullOrWhiteSpace(fileName))
            {
                fileName = FileNameFromContentDisposition(e.DownloadOperation == null ? string.Empty : e.DownloadOperation.ContentDisposition);
            }
            if (string.IsNullOrWhiteSpace(fileName))
            {
                fileName = FileNameFromUri(e.DownloadOperation == null ? string.Empty : e.DownloadOperation.Uri);
            }
            if (string.IsNullOrWhiteSpace(fileName))
            {
                fileName = "soai-download-" + DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture);
            }
            return SanitizeFileName(fileName);
        }

        public static string ResolveUniquePath(string directory, string fileName)
        {
            string safeName = SanitizeFileName(fileName);
            string candidate = Path.Combine(directory, safeName);
            if (!File.Exists(candidate))
            {
                return candidate;
            }

            string name = Path.GetFileNameWithoutExtension(safeName);
            string extension = Path.GetExtension(safeName);
            for (int i = 1; i < 10000; i++)
            {
                candidate = Path.Combine(directory, name + " (" + i.ToString(CultureInfo.InvariantCulture) + ")" + extension);
                if (!File.Exists(candidate))
                {
                    return candidate;
                }
            }
            return Path.Combine(directory, name + "-" + Guid.NewGuid().ToString("N") + extension);
        }

        private static string FileNameFromPath(string path)
        {
            try
            {
                return Path.GetFileName(path ?? string.Empty);
            }
            catch
            {
                return string.Empty;
            }
        }

        private static string FileNameFromUri(string value)
        {
            Uri uri;
            if (!Uri.TryCreate(value, UriKind.Absolute, out uri))
            {
                return string.Empty;
            }
            return FileNameFromPath(Uri.UnescapeDataString(uri.LocalPath));
        }

        private static string FileNameFromContentDisposition(string value)
        {
            string text = value ?? string.Empty;
            string extended = ExtractContentDispositionValue(text, "filename*=");
            if (!string.IsNullOrWhiteSpace(extended))
            {
                int charsetSeparator = extended.IndexOf("''", StringComparison.Ordinal);
                if (charsetSeparator >= 0)
                {
                    extended = extended.Substring(charsetSeparator + 2);
                }
                return FileNameFromPath(Uri.UnescapeDataString(extended));
            }

            string fileName = ExtractContentDispositionValue(text, "filename=");
            return FileNameFromPath(fileName);
        }

        private static string ExtractContentDispositionValue(string text, string key)
        {
            int index = text.IndexOf(key, StringComparison.OrdinalIgnoreCase);
            if (index < 0)
            {
                return string.Empty;
            }
            string value = text.Substring(index + key.Length).Trim();
            int semicolon = value.IndexOf(';');
            if (semicolon >= 0)
            {
                value = value.Substring(0, semicolon).Trim();
            }
            if (value.Length >= 2 && value[0] == '"' && value[value.Length - 1] == '"')
            {
                value = value.Substring(1, value.Length - 2);
            }
            return value;
        }

        private static string SanitizeFileName(string value)
        {
            string name = FileNameFromPath(value);
            if (string.IsNullOrWhiteSpace(name))
            {
                name = "soai-download";
            }
            foreach (char invalid in Path.GetInvalidFileNameChars())
            {
                name = name.Replace(invalid, '_');
            }
            name = name.Trim().TrimEnd('.');
            return string.IsNullOrWhiteSpace(name) ? "soai-download" : name;
        }
    }

    internal static class UnelevatedLauncher
    {
        private const string HandoffArgument = "--soai-medium-ui-handoff";
        private const uint PROCESS_CREATE_PROCESS = 0x00000080;
        private const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x00001000;
        private const uint TOKEN_DUPLICATE = 0x00000002;
        private const uint TOKEN_QUERY = 0x00000008;
        private const uint CREATE_SUSPENDED = 0x00000004;
        private const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400;
        private const uint EXTENDED_STARTUPINFO_PRESENT = 0x00080000;
        private const uint FULL_OBJECT_ACCESS = 0x001FFFFF;
        private const int ERROR_BAD_LENGTH = 24;
        private const int ERROR_INSUFFICIENT_BUFFER = 122;
        private const int TOKEN_USER_CLASS = 1;
        private const int TOKEN_PRIMARY_GROUP_CLASS = 5;
        private const int TOKEN_DEFAULT_DACL_CLASS = 6;
        private const int TOKEN_SESSION_ID_CLASS = 12;
        private const int TOKEN_ELEVATION_CLASS = 20;
        private const int TOKEN_INTEGRITY_LEVEL_CLASS = 25;
        private const int SECURITY_IDENTIFICATION = 1;
        private const int SE_KERNEL_OBJECT = 6;
        private const uint OWNER_SECURITY_INFORMATION = 0x00000001;
        private const uint GROUP_SECURITY_INFORMATION = 0x00000002;
        private const uint DACL_SECURITY_INFORMATION = 0x00000004;
        private const uint LABEL_SECURITY_INFORMATION = 0x00000010;
        private const int SYSTEM_MANDATORY_LABEL_NO_WRITE_UP = 0x1;
        private const int SYSTEM_MANDATORY_LABEL_NO_READ_UP = 0x2;
        private const byte SYSTEM_MANDATORY_LABEL_ACE_TYPE = 0x11;
        private const int SE_DACL_PRESENT = 0x0004;
        private const int SE_SACL_PRESENT = 0x0010;
        private const int SE_SELF_RELATIVE = 0x8000;
        private const int DESCRIPTOR_HEADER_LENGTH = 20;
        private const int ACL_HEADER_LENGTH = 8;
        private const int ACE_HEADER_LENGTH = 4;
        private static readonly SecurityIdentifier MediumIntegrity = new SecurityIdentifier("S-1-16-8192");
        private static readonly IntPtr PROC_THREAD_ATTRIBUTE_PARENT_PROCESS = new IntPtr(0x00020000);

        public static bool IsHandoffCommand(string[] args)
        {
            return args != null && Array.Exists(args, delegate(string value) { return string.Equals(value, HandoffArgument, StringComparison.Ordinal); });
        }

        public static string[] CompleteHandoff(string[] args)
        {
            List<string> filtered = new List<string>();
            foreach (string arg in args ?? new string[0])
            {
                if (!string.Equals(arg, HandoffArgument, StringComparison.Ordinal))
                {
                    filtered.Add(arg);
                }
            }
            return filtered.ToArray();
        }

        public static bool TryLaunch(LauncherPaths paths, string image, string[] args)
        {
            try
            {
                if (!string.Equals(LauncherPaths.FromRoot(Path.GetDirectoryName(image)).RootDirectory, paths.RootDirectory, StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException("The SoAI program file is not in its verified installation folder.");
                }
                List<string> forwarded = new List<string>(CompleteHandoff(args));
                forwarded.Add(HandoffArgument);
                StartFromDesktopShell(image, paths.RootDirectory, forwarded.ToArray());
                return true;
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                MessageBox.Show("SoAI could not start in the standard desktop session. Start SoAI from its desktop shortcut.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return false;
            }
        }

        public static void StartFromDesktopShell(string executable, string workingDirectory, string[] args)
        {
            IntPtr shellProcess = OpenDesktopShell();
            IntPtr shellToken = IntPtr.Zero;
            IntPtr securityDescriptor = IntPtr.Zero;
            IntPtr environment = IntPtr.Zero;
            IntPtr attributeList = IntPtr.Zero;
            IntPtr parentProcessValue = IntPtr.Zero;
            PROCESS_INFORMATION processInformation = new PROCESS_INFORMATION();
            bool attributeListInitialized = false;
            bool processResumed = false;
            try
            {
                if (!OpenProcessToken(shellProcess, TOKEN_QUERY | TOKEN_DUPLICATE, out shellToken))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to inspect the Windows desktop shell token.");
                }
                SecurityIdentifier user;
                int session;
                IntPtr currentToken;
                if (!OpenProcessToken(NativeBackendJob.GetCurrentProcess(), TOKEN_QUERY, out currentToken))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to inspect the SoAI launcher token.");
                }
                try
                {
                    user = ReadTokenSid(currentToken, TOKEN_USER_CLASS);
                    session = ReadTokenInformation(currentToken, TOKEN_SESSION_ID_CLASS, Marshal.ReadInt32);
                }
                finally { CloseHandle(currentToken); }
                RequireStandardDesktopToken(shellToken, user, session, "The Windows desktop shell");
                byte[] descriptor = BuildDesktopObjectSecurity(user, ReadTokenSid(shellToken, TOKEN_PRIMARY_GROUP_CLASS), ReadTokenDefaultDacl(shellToken));
                securityDescriptor = Marshal.AllocHGlobal(descriptor.Length);
                Marshal.Copy(descriptor, 0, securityDescriptor, descriptor.Length);
                SECURITY_ATTRIBUTES processSecurity = new SECURITY_ATTRIBUTES();
                processSecurity.nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES));
                processSecurity.lpSecurityDescriptor = securityDescriptor;
                SECURITY_ATTRIBUTES threadSecurity = processSecurity;
                if (!CreateEnvironmentBlock(out environment, shellToken, false))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to build the standard desktop user's environment.");
                }
                IntPtr attributeListSize = IntPtr.Zero;
                if (!InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref attributeListSize))
                {
                    int sizingError = Marshal.GetLastWin32Error();
                    if (sizingError != ERROR_INSUFFICIENT_BUFFER || attributeListSize == IntPtr.Zero)
                    {
                        throw new Win32Exception(sizingError, "Failed to size the desktop process attributes.");
                    }
                }
                attributeList = Marshal.AllocHGlobal(attributeListSize);
                if (!InitializeProcThreadAttributeList(attributeList, 1, 0, ref attributeListSize))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to initialize the desktop process attributes.");
                }
                attributeListInitialized = true;
                parentProcessValue = Marshal.AllocHGlobal(IntPtr.Size);
                Marshal.WriteIntPtr(parentProcessValue, shellProcess);
                if (!UpdateProcThreadAttribute(attributeList, 0, PROC_THREAD_ATTRIBUTE_PARENT_PROCESS, parentProcessValue, new IntPtr(IntPtr.Size), IntPtr.Zero, IntPtr.Zero))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to select the Windows desktop shell as the launcher parent.");
                }
                STARTUPINFOEX startupInformation = new STARTUPINFOEX();
                startupInformation.StartupInfo.cb = Marshal.SizeOf(typeof(STARTUPINFOEX));
                startupInformation.AttributeList = attributeList;
                string application = NativeBackendJob.ResolveProcessPath(executable);
                StringBuilder commandLine = new StringBuilder(BackendProcess.Quote(application) + BackendProcess.BuildArgumentString(args));
                if (!CreateProcess(application, commandLine, ref processSecurity, ref threadSecurity, false, CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT, environment, NativeBackendJob.ResolveProcessPath(workingDirectory, true), ref startupInformation, out processInformation))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to start SoAI from the Windows desktop shell.");
                }
                RequireDesktopChild(processInformation, executable, user, session);
                if (ResumeThread(processInformation.hThread) == UInt32.MaxValue)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to resume SoAI in the standard desktop session.");
                }
                processResumed = true;
            }
            catch (Exception failure)
            {
                if (processInformation.hProcess == IntPtr.Zero || processResumed)
                {
                    throw;
                }
                try
                {
                    NativeBackendJob.StopIncompleteProcess(processInformation.hProcess, "unverified desktop launcher");
                }
                catch (Exception cleanupFailure)
                {
                    throw new AggregateException("SoAI could not start in the standard desktop session, and its suspended launcher could not be stopped.", failure, cleanupFailure);
                }
                throw;
            }
            finally
            {
                if (processInformation.hThread != IntPtr.Zero)
                {
                    CloseHandle(processInformation.hThread);
                }
                if (processInformation.hProcess != IntPtr.Zero)
                {
                    CloseHandle(processInformation.hProcess);
                }
                if (parentProcessValue != IntPtr.Zero)
                {
                    Marshal.FreeHGlobal(parentProcessValue);
                }
                if (attributeListInitialized)
                {
                    DeleteProcThreadAttributeList(attributeList);
                }
                if (attributeList != IntPtr.Zero)
                {
                    Marshal.FreeHGlobal(attributeList);
                }
                if (environment != IntPtr.Zero)
                {
                    DestroyEnvironmentBlock(environment);
                }
                if (securityDescriptor != IntPtr.Zero)
                {
                    Marshal.FreeHGlobal(securityDescriptor);
                }
                if (shellToken != IntPtr.Zero)
                {
                    CloseHandle(shellToken);
                }
                CloseHandle(shellProcess);
            }
        }

        internal static byte[] BuildDesktopObjectSecurity(SecurityIdentifier owner, SecurityIdentifier group, byte[] defaultDacl)
        {
            if (defaultDacl == null || defaultDacl.Length < ACL_HEADER_LENGTH || BitConverter.ToUInt16(defaultDacl, 2) != defaultDacl.Length)
            {
                throw new InvalidOperationException("The Windows desktop shell has no usable default access control list for SoAI's process.");
            }
            new RawAcl(defaultDacl, 0);
            int labelLength = ACE_HEADER_LENGTH + 4 + MediumIntegrity.BinaryLength;
            byte[] systemAcl = new byte[ACL_HEADER_LENGTH + labelLength];
            systemAcl[0] = (byte)GenericAcl.AclRevision;
            BitConverter.GetBytes((ushort)systemAcl.Length).CopyTo(systemAcl, 2);
            BitConverter.GetBytes((ushort)1).CopyTo(systemAcl, 4);
            systemAcl[ACL_HEADER_LENGTH] = SYSTEM_MANDATORY_LABEL_ACE_TYPE;
            BitConverter.GetBytes((ushort)labelLength).CopyTo(systemAcl, ACL_HEADER_LENGTH + 2);
            BitConverter.GetBytes(SYSTEM_MANDATORY_LABEL_NO_WRITE_UP | SYSTEM_MANDATORY_LABEL_NO_READ_UP).CopyTo(systemAcl, ACL_HEADER_LENGTH + ACE_HEADER_LENGTH);
            MediumIntegrity.GetBinaryForm(systemAcl, ACL_HEADER_LENGTH + ACE_HEADER_LENGTH + 4);
            byte[] descriptor = new byte[DESCRIPTOR_HEADER_LENGTH + owner.BinaryLength + group.BinaryLength + systemAcl.Length + defaultDacl.Length];
            descriptor[0] = 1;
            BitConverter.GetBytes((ushort)(SE_DACL_PRESENT | SE_SACL_PRESENT | SE_SELF_RELATIVE)).CopyTo(descriptor, 2);
            int offset = DESCRIPTOR_HEADER_LENGTH;
            BitConverter.GetBytes(offset).CopyTo(descriptor, 4);
            owner.GetBinaryForm(descriptor, offset);
            offset += owner.BinaryLength;
            BitConverter.GetBytes(offset).CopyTo(descriptor, 8);
            group.GetBinaryForm(descriptor, offset);
            offset += group.BinaryLength;
            BitConverter.GetBytes(offset).CopyTo(descriptor, 12);
            systemAcl.CopyTo(descriptor, offset);
            offset += systemAcl.Length;
            BitConverter.GetBytes(offset).CopyTo(descriptor, 16);
            defaultDacl.CopyTo(descriptor, offset);
            return descriptor;
        }

        internal static SecurityIdentifier ReadMandatoryLabel(byte[] descriptor)
        {
            SecurityIdentifier integrity = null;
            int systemAcl = descriptor.Length >= DESCRIPTOR_HEADER_LENGTH && (BitConverter.ToUInt16(descriptor, 2) & SE_SACL_PRESENT) != 0 ? BitConverter.ToInt32(descriptor, 12) : 0;
            if (systemAcl > 0)
            {
                if (systemAcl > descriptor.Length - ACL_HEADER_LENGTH || BitConverter.ToUInt16(descriptor, systemAcl + 2) > descriptor.Length - systemAcl)
                {
                    throw new InvalidOperationException("The SoAI launcher process carries a malformed Windows integrity label.");
                }
                int end = systemAcl + BitConverter.ToUInt16(descriptor, systemAcl + 2);
                int entry = systemAcl + ACL_HEADER_LENGTH;
                for (int index = BitConverter.ToUInt16(descriptor, systemAcl + 4); index > 0; index--)
                {
                    int entryLength = entry <= end - ACE_HEADER_LENGTH ? BitConverter.ToUInt16(descriptor, entry + 2) : 0;
                    if (entryLength < ACE_HEADER_LENGTH || entryLength > end - entry)
                    {
                        throw new InvalidOperationException("The SoAI launcher process carries a malformed Windows integrity label.");
                    }
                    if (descriptor[entry] == SYSTEM_MANDATORY_LABEL_ACE_TYPE)
                    {
                        if (integrity != null || entryLength < ACE_HEADER_LENGTH + 4 + 8 || descriptor[entry + ACE_HEADER_LENGTH + 4] != 1)
                        {
                            throw new InvalidOperationException("The SoAI launcher process carries an ambiguous Windows integrity label.");
                        }
                        integrity = new SecurityIdentifier(descriptor, entry + ACE_HEADER_LENGTH + 4);
                        if (integrity.BinaryLength > entryLength - ACE_HEADER_LENGTH - 4)
                        {
                            throw new InvalidOperationException("The SoAI launcher process carries a malformed Windows integrity label.");
                        }
                    }
                    entry += entryLength;
                }
            }
            if (integrity == null)
            {
                throw new InvalidOperationException("The SoAI launcher process has no explicit Windows integrity label.");
            }
            return integrity;
        }

        private static IntPtr OpenDesktopShell()
        {
            int shellProcessId = ReadDesktopShellProcessId();
            IntPtr shellProcess = OpenProcess(PROCESS_CREATE_PROCESS | PROCESS_QUERY_LIMITED_INFORMATION, false, shellProcessId);
            if (shellProcess == IntPtr.Zero)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to open the Windows desktop shell.");
            }
            try
            {
                if (ReadDesktopShellProcessId() != shellProcessId)
                {
                    throw new InvalidOperationException("The Windows desktop shell changed while SoAI was starting.");
                }
                return shellProcess;
            }
            catch
            {
                CloseHandle(shellProcess);
                throw;
            }
        }

        private static int ReadDesktopShellProcessId()
        {
            IntPtr shellWindow = GetShellWindow();
            if (shellWindow == IntPtr.Zero)
            {
                throw new InvalidOperationException("The Windows desktop shell is not available.");
            }
            int shellProcessId;
            if (GetWindowThreadProcessId(shellWindow, out shellProcessId) == 0 || shellProcessId <= 0)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to identify the Windows desktop shell.");
            }
            return shellProcessId;
        }

        private static void RequireDesktopChild(PROCESS_INFORMATION child, string executable, SecurityIdentifier user, int session)
        {
            if (!string.Equals(Path.GetFullPath(NativeBackendJob.ReadProcessImagePath(child.hProcess)), Path.GetFullPath(executable), StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("The desktop launcher process does not run the verified SoAI program file.");
            }
            IntPtr token;
            if (!OpenProcessToken(child.hProcess, TOKEN_QUERY | TOKEN_DUPLICATE, out token))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to inspect the desktop launcher token.");
            }
            IntPtr identification = IntPtr.Zero;
            try
            {
                RequireStandardDesktopToken(token, user, session, "The desktop launcher");
                if (!DuplicateToken(token, SECURITY_IDENTIFICATION, out identification))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to prepare the desktop launcher access check.");
                }
                GENERIC_MAPPING processMapping = new GENERIC_MAPPING { GenericRead = 0x00020410, GenericWrite = 0x00020BEA, GenericExecute = 0x00121000, GenericAll = 0x001FFFFF };
                GENERIC_MAPPING threadMapping = new GENERIC_MAPPING { GenericRead = 0x00020048, GenericWrite = 0x00020437, GenericExecute = 0x00121800, GenericAll = 0x001FFFFF };
                RequireUsableObject(child.hProcess, identification, processMapping, "The desktop launcher process");
                RequireUsableObject(child.hThread, identification, threadMapping, "The desktop launcher thread");
            }
            finally
            {
                if (identification != IntPtr.Zero)
                {
                    CloseHandle(identification);
                }
                CloseHandle(token);
            }
        }

        private static void RequireStandardDesktopToken(IntPtr token, SecurityIdentifier user, int session, string subject)
        {
            if (!ReadTokenSid(token, TOKEN_USER_CLASS).Equals(user))
            {
                throw new InvalidOperationException(subject + " belongs to a different Windows user than the SoAI launcher.");
            }
            if (ReadTokenInformation(token, TOKEN_SESSION_ID_CLASS, Marshal.ReadInt32) != session)
            {
                throw new InvalidOperationException(subject + " is in a different Windows session than the SoAI launcher.");
            }
            if (ReadTokenInformation(token, TOKEN_ELEVATION_CLASS, Marshal.ReadInt32) != 0)
            {
                throw new InvalidOperationException(subject + " did not provide a standard-user process token.");
            }
            if (!ReadTokenSid(token, TOKEN_INTEGRITY_LEVEL_CLASS).Equals(MediumIntegrity))
            {
                throw new InvalidOperationException(subject + " does not run at the standard desktop integrity level.");
            }
        }

        private static void RequireUsableObject(IntPtr handle, IntPtr identification, GENERIC_MAPPING mapping, string subject)
        {
            IntPtr owner;
            IntPtr group;
            IntPtr dacl;
            IntPtr sacl;
            IntPtr descriptor;
            uint result = GetSecurityInfo(handle, SE_KERNEL_OBJECT, OWNER_SECURITY_INFORMATION | GROUP_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION | LABEL_SECURITY_INFORMATION, out owner, out group, out dacl, out sacl, out descriptor);
            if (result != 0)
            {
                throw new Win32Exception((int)result, "Failed to inspect the security of " + subject.ToLowerInvariant() + ".");
            }
            IntPtr privileges = IntPtr.Zero;
            try
            {
                byte[] binary = new byte[GetSecurityDescriptorLength(descriptor)];
                Marshal.Copy(descriptor, binary, 0, binary.Length);
                if (!ReadMandatoryLabel(binary).Equals(MediumIntegrity))
                {
                    throw new InvalidOperationException(subject + " carries an integrity label above the standard desktop level.");
                }
                int privilegeLength = 256;
                privileges = Marshal.AllocHGlobal(privilegeLength);
                uint granted;
                bool allowed;
                if (!AccessCheck(descriptor, identification, FULL_OBJECT_ACCESS, ref mapping, privileges, ref privilegeLength, out granted, out allowed))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to verify access to " + subject.ToLowerInvariant() + ".");
                }
                if (!allowed || granted != FULL_OBJECT_ACCESS)
                {
                    throw new InvalidOperationException(subject + " would not be usable by its own standard desktop token.");
                }
            }
            finally
            {
                if (privileges != IntPtr.Zero)
                {
                    Marshal.FreeHGlobal(privileges);
                }
                LocalFree(descriptor);
            }
        }

        private static SecurityIdentifier ReadTokenSid(IntPtr token, int informationClass)
        {
            return ReadTokenInformation(token, informationClass, delegate(IntPtr buffer) { return new SecurityIdentifier(Marshal.ReadIntPtr(buffer)); });
        }

        private static byte[] ReadTokenDefaultDacl(IntPtr token)
        {
            return ReadTokenInformation(token, TOKEN_DEFAULT_DACL_CLASS, delegate(IntPtr buffer)
            {
                IntPtr acl = Marshal.ReadIntPtr(buffer);
                if (acl == IntPtr.Zero)
                {
                    return null;
                }
                byte[] binary = new byte[(ushort)Marshal.ReadInt16(acl, 2)];
                Marshal.Copy(acl, binary, 0, binary.Length);
                return binary;
            });
        }

        private static T ReadTokenInformation<T>(IntPtr token, int informationClass, Func<IntPtr, T> read)
        {
            int length;
            if (!GetTokenInformation(token, informationClass, IntPtr.Zero, 0, out length))
            {
                int sizingError = Marshal.GetLastWin32Error();
                if ((sizingError != ERROR_INSUFFICIENT_BUFFER && sizingError != ERROR_BAD_LENGTH) || length <= 0)
                {
                    throw new Win32Exception(sizingError, "Failed to read Windows desktop token information.");
                }
            }
            IntPtr buffer = Marshal.AllocHGlobal(length);
            try
            {
                if (!GetTokenInformation(token, informationClass, buffer, length, out length))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to read Windows desktop token information.");
                }
                return read(buffer);
            }
            finally { Marshal.FreeHGlobal(buffer); }
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct STARTUPINFO
        {
            public int cb;
            public string lpReserved;
            public string lpDesktop;
            public string lpTitle;
            public int dwX;
            public int dwY;
            public int dwXSize;
            public int dwYSize;
            public int dwXCountChars;
            public int dwYCountChars;
            public int dwFillAttribute;
            public uint dwFlags;
            public short wShowWindow;
            public short cbReserved2;
            public IntPtr lpReserved2;
            public IntPtr hStdInput;
            public IntPtr hStdOutput;
            public IntPtr hStdError;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct STARTUPINFOEX
        {
            public STARTUPINFO StartupInfo;
            public IntPtr AttributeList;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_INFORMATION
        {
            public IntPtr hProcess;
            public IntPtr hThread;
            public int dwProcessId;
            public int dwThreadId;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SECURITY_ATTRIBUTES
        {
            public int nLength;
            public IntPtr lpSecurityDescriptor;
            public int bInheritHandle;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct GENERIC_MAPPING
        {
            public uint GenericRead;
            public uint GenericWrite;
            public uint GenericExecute;
            public uint GenericAll;
        }

        [DllImport("user32.dll")]
        private static extern IntPtr GetShellWindow();

        [DllImport("user32.dll", SetLastError = true)]
        private static extern uint GetWindowThreadProcessId(IntPtr window, out int processId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint desiredAccess, bool inheritHandle, int processId);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool OpenProcessToken(IntPtr processHandle, uint desiredAccess, out IntPtr tokenHandle);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool GetTokenInformation(IntPtr tokenHandle, int tokenInformationClass, IntPtr tokenInformation, int tokenInformationLength, out int returnLength);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool DuplicateToken(IntPtr existingToken, int impersonationLevel, out IntPtr duplicateToken);

        [DllImport("advapi32.dll")]
        private static extern uint GetSecurityInfo(IntPtr handle, int objectType, uint securityInformation, out IntPtr owner, out IntPtr group, out IntPtr dacl, out IntPtr sacl, out IntPtr securityDescriptor);

        [DllImport("advapi32.dll")]
        private static extern uint GetSecurityDescriptorLength(IntPtr securityDescriptor);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool AccessCheck(IntPtr securityDescriptor, IntPtr clientToken, uint desiredAccess, ref GENERIC_MAPPING genericMapping, IntPtr privilegeSet, ref int privilegeSetLength, out uint grantedAccess, out bool accessStatus);

        [DllImport("userenv.dll", SetLastError = true)]
        private static extern bool CreateEnvironmentBlock(out IntPtr environment, IntPtr token, bool inherit);

        [DllImport("userenv.dll", SetLastError = true)]
        private static extern bool DestroyEnvironmentBlock(IntPtr environment);

        [DllImport("kernel32.dll")]
        private static extern IntPtr LocalFree(IntPtr memory);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool InitializeProcThreadAttributeList(IntPtr attributeList, int attributeCount, int flags, ref IntPtr size);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool UpdateProcThreadAttribute(IntPtr attributeList, uint flags, IntPtr attribute, IntPtr value, IntPtr size, IntPtr previousValue, IntPtr returnSize);

        [DllImport("kernel32.dll")]
        private static extern void DeleteProcThreadAttributeList(IntPtr attributeList);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateProcess(string applicationName, StringBuilder commandLine, ref SECURITY_ATTRIBUTES processAttributes, ref SECURITY_ATTRIBUTES threadAttributes, bool inheritHandles, uint creationFlags, IntPtr environment, string currentDirectory, ref STARTUPINFOEX startupInformation, out PROCESS_INFORMATION processInformation);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint ResumeThread(IntPtr thread);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);
    }

    internal sealed class UpdateRestorationRequiredException : Exception
    {
        public UpdateRestorationRequiredException(string transactionPath)
            : base("SoAI must restore the previous version after an interrupted update.")
        {
            TransactionPath = transactionPath;
        }

        public string TransactionPath { get; private set; }
    }

    internal sealed class InstallationSecurityRequiredException : Exception
    {
        public InstallationSecurityRequiredException()
            : base("SoAI could not finish securing its installation after the update. Restart SoAI to complete the installation.")
        {
        }
    }

    internal sealed class BackendServiceSession : IDisposable
    {
        private static readonly TimeSpan ConnectionTimeout = TimeSpan.FromMinutes(2);
        private static readonly TimeSpan EndpointConfirmationTimeout = TimeSpan.FromSeconds(60);
        private static readonly TimeSpan MessageTimeout = TimeSpan.FromSeconds(10);
        private const string DiagnosticsLocation = "Service diagnostics are in soai-service.log in the SoAI data\\logs folder.";
        private readonly NamedPipeClientStream pipe;
        private readonly StreamReader reader;
        private readonly StreamWriter writer;
        private string pendingMessage;
        private bool ready;
        private bool released;

        private BackendServiceSession(NamedPipeClientStream pipe, StreamReader reader, StreamWriter writer, string firstMessage)
        {
            this.pipe = pipe;
            this.reader = reader;
            this.writer = writer;
            this.pendingMessage = firstMessage;
        }

        public static async Task<BackendServiceSession> OpenAsync(LauncherPaths paths, CancellationToken token)
        {
            Stopwatch elapsed = Stopwatch.StartNew();
            bool startRequested = false;
            while (true)
            {
                token.ThrowIfCancellationRequested();
                int serviceProcessId = ServiceRegistration.EnsureRunning(paths, ref startRequested);
                if (serviceProcessId != 0)
                {
                    BackendServiceSession session = await TryConnectAsync(paths, serviceProcessId, token);
                    if (session != null)
                    {
                        return session;
                    }
                }
                if (elapsed.Elapsed >= ConnectionTimeout)
                {
                    throw new TimeoutException("The SoAI background service did not accept this window within 2 minutes. Restart Windows, then start SoAI again. " + DiagnosticsLocation);
                }
                await Task.Delay(250, token);
            }
        }

        private static async Task<BackendServiceSession> TryConnectAsync(LauncherPaths paths, int serviceProcessId, CancellationToken token)
        {
            NamedPipeClientStream pipe = new NamedPipeClientStream(
                ".",
                ServiceRegistration.PipeName(paths),
                PipeAccessRights.ReadData | PipeAccessRights.WriteData | PipeAccessRights.ReadAttributes,
                PipeOptions.Asynchronous,
                TokenImpersonationLevel.Identification,
                HandleInheritability.None);
            bool connected = false;
            try
            {
                try
                {
                    await pipe.ConnectAsync(2000, token);
                }
                catch (TimeoutException)
                {
                    return null;
                }
                catch (IOException)
                {
                    return null;
                }
                catch (UnauthorizedAccessException exception)
                {
                    throw new InvalidOperationException("This Windows account cannot use the SoAI background service. Sign in to Windows interactively, then start SoAI again.", exception);
                }
                uint serverProcessId;
                if (!GetNamedPipeServerProcessId(pipe.SafePipeHandle, out serverProcessId))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "SoAI could not identify its background service.");
                }
                int runningProcessId = ServiceRegistration.QueryRunningProcessId(paths);
                if (runningProcessId == 0)
                {
                    return null;
                }
                if (serverProcessId != (uint)runningProcessId || runningProcessId != serviceProcessId)
                {
                    throw new InvalidOperationException("SoAI could not verify its background service. Restart Windows, then start SoAI again.");
                }
                StreamReader reader = new StreamReader(pipe, new UTF8Encoding(false), false, 1024, true);
                StreamWriter writer = new StreamWriter(pipe, new UTF8Encoding(false), 1024, true);
                writer.AutoFlush = true;
                Task<string> greetingRead = reader.ReadLineAsync();
                Task greetingCompleted = await Task.WhenAny(greetingRead, Task.Delay(MessageTimeout, token));
                if (greetingCompleted != greetingRead)
                {
                    token.ThrowIfCancellationRequested();
                    throw new TimeoutException("The SoAI background service did not answer within 10 seconds. " + DiagnosticsLocation);
                }
                string greeting;
                try
                {
                    greeting = await greetingRead;
                }
                catch (IOException)
                {
                    greeting = null;
                }
                if (greeting == null)
                {
                    return null;
                }
                connected = true;
                return new BackendServiceSession(pipe, reader, writer, greeting);
            }
            finally
            {
                if (!connected)
                {
                    pipe.Dispose();
                }
            }
        }

        public async Task<EndpointInfo> WaitForReadyAsync(SplashView splash, NativeImageAllowance readiness, CancellationToken token)
        {
            Stopwatch elapsed = Stopwatch.StartNew();
            TimeSpan timeout = readiness.Duration + MessageTimeout;
            Task<string> pendingRead = null;
            try
            {
                while (elapsed.Elapsed < timeout)
                {
                    token.ThrowIfCancellationRequested();
                    string message;
                    if (pendingMessage != null)
                    {
                        message = pendingMessage;
                        pendingMessage = null;
                    }
                    else
                    {
                        if (pendingRead == null)
                        {
                            pendingRead = reader.ReadLineAsync();
                        }
                        Task completed = await Task.WhenAny(pendingRead, Task.Delay(500, token));
                        if (completed != pendingRead)
                        {
                            continue;
                        }
                        try
                        {
                            message = await pendingRead;
                        }
                        catch (IOException)
                        {
                            message = null;
                        }
                        pendingRead = null;
                    }
                    if (message == null)
                    {
                        throw new InvalidOperationException("The SoAI background service stopped before SoAI became ready. " + DiagnosticsLocation);
                    }
                    if (message.StartsWith("STATUS\t", StringComparison.Ordinal))
                    {
                        splash.SetStatus(message.Substring(7));
                    }
                    else if (string.Equals(message, "READY", StringComparison.Ordinal))
                    {
                        return await CommitAsync(splash, token);
                    }
                    else if (message.StartsWith("ERROR\t", StringComparison.Ordinal))
                    {
                        throw new InvalidOperationException(message.Substring(6));
                    }
                    else if (message.StartsWith("RESTORE\t", StringComparison.Ordinal))
                    {
                        throw new UpdateRestorationRequiredException(message.Substring(8));
                    }
                    else
                    {
                        throw new InvalidOperationException("The SoAI background service sent an unexpected message.");
                    }
                }
                throw new TimeoutException(readiness.DescribeTimeout("SoAI") + " " + DiagnosticsLocation);
            }
            catch
            {
                TryCancel();
                throw;
            }
        }

        private async Task<EndpointInfo> CommitAsync(SplashView splash, CancellationToken token)
        {
            EndpointInfo endpoint = await DiscoveryProbe.WaitForEndpointAsync(TimeSpan.FromMilliseconds(250), EndpointConfirmationTimeout, token);
            if (endpoint == null || !await HealthProbe.WaitForReadyAsync(endpoint, TimeSpan.FromMilliseconds(250), EndpointConfirmationTimeout, token))
            {
                throw new InvalidOperationException("The SoAI background service reported readiness without a healthy endpoint. " + DiagnosticsLocation);
            }
            writer.WriteLine("COMMIT");
            Task<string> commitRead = reader.ReadLineAsync();
            Task commitCompleted = await Task.WhenAny(commitRead, Task.Delay(MessageTimeout, token));
            if (commitCompleted != commitRead)
            {
                token.ThrowIfCancellationRequested();
                throw new TimeoutException("The SoAI background service did not confirm this window.");
            }
            if (!string.Equals(await commitRead, "COMMITTED", StringComparison.Ordinal))
            {
                throw new InvalidOperationException("The SoAI background service did not confirm this window.");
            }
            ready = true;
            splash.SetStatus("SoAI is ready...");
            return endpoint;
        }

        private void TryCancel()
        {
            try
            {
                if (pipe.IsConnected)
                {
                    writer.WriteLine("CANCEL");
                }
            }
            catch (IOException)
            {
            }
            catch (ObjectDisposedException)
            {
            }
        }

        public void Release(bool stopBackend)
        {
            try
            {
                if (!released)
                {
                    released = true;
                    if (ready && pipe.IsConnected)
                    {
                        writer.WriteLine(stopBackend ? "STOP" : "RELEASE");
                    }
                    else
                    {
                        TryCancel();
                    }
                }
            }
            finally
            {
                Dispose();
            }
        }

        public void Dispose()
        {
            if (!released)
            {
                released = true;
                TryCancel();
            }
            try
            {
                writer.Dispose();
            }
            catch (IOException)
            {
            }
            finally
            {
                try
                {
                    reader.Dispose();
                }
                finally
                {
                    pipe.Dispose();
                }
            }
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool GetNamedPipeServerProcessId(SafePipeHandle pipe, out uint serverProcessId);
    }

    internal sealed class BackendServiceConnection
    {
        private const int MaximumMessageLength = 64;
        private readonly NamedPipeServerStream pipe;
        private readonly StreamReader reader;
        private readonly StreamWriter writer;
        private readonly object writeLock = new object();
        private readonly char[] buffer = new char[1];

        public BackendServiceConnection(NamedPipeServerStream pipe)
        {
            this.pipe = pipe;
            this.reader = new StreamReader(pipe, new UTF8Encoding(false), false, 1024, true);
            this.writer = new StreamWriter(pipe, new UTF8Encoding(false), 1024, true);
            this.writer.AutoFlush = true;
        }

        public bool ReadySent { get; private set; }

        public bool Committed { get; set; }

        public async Task<string> ReadMessageAsync()
        {
            StringBuilder message = new StringBuilder();
            while (true)
            {
                if (await reader.ReadAsync(buffer, 0, 1) == 0)
                {
                    return null;
                }
                if (buffer[0] == '\n')
                {
                    return message.ToString().TrimEnd('\r');
                }
                if (message.Length >= MaximumMessageLength)
                {
                    throw new InvalidDataException("A SoAI window sent an oversized service message.");
                }
                message.Append(buffer[0]);
            }
        }

        public void Send(string message)
        {
            lock (writeLock)
            {
                try
                {
                    writer.WriteLine(message);
                    if (string.Equals(message, "READY", StringComparison.Ordinal))
                    {
                        ReadySent = true;
                    }
                }
                catch (IOException)
                {
                }
                catch (ObjectDisposedException)
                {
                }
            }
        }

        public void Close()
        {
            lock (writeLock)
            {
                try
                {
                    writer.Dispose();
                }
                catch (IOException)
                {
                }
                finally
                {
                    try
                    {
                        reader.Dispose();
                    }
                    finally
                    {
                        pipe.Dispose();
                    }
                }
            }
        }
    }

    internal sealed class BackendService : System.ServiceProcess.ServiceBase
    {
        private const string PipeSecurity = "D:P(A;;GA;;;SY)(A;;0x12019b;;;IU)";
        private const string DiagnosticsLocation = "Service diagnostics are in soai-service.log in the SoAI data\\logs folder.";
        private const uint PIPE_ACCESS_DUPLEX = 0x00000003;
        private const uint FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000;
        private const uint FILE_FLAG_OVERLAPPED = 0x40000000;
        private const uint PIPE_REJECT_REMOTE_CLIENTS = 0x00000008;
        private const uint PIPE_UNLIMITED_INSTANCES = 255;
        private static readonly string[] BackendArguments = new string[] { "start", "--start-no-browser" };
        private static readonly TimeSpan BackendStartupTimeout = TimeSpan.FromMinutes(20);
        private static readonly TimeSpan BackendStopTimeout = TimeSpan.FromSeconds(150);
        private static readonly TimeSpan SystemShutdownStopTimeout = TimeSpan.FromSeconds(15);
        private static readonly TimeSpan SupervisionInterval = TimeSpan.FromSeconds(1);
        private readonly LauncherPaths paths;
        private readonly object sync = new object();
        private readonly List<BackendServiceConnection> connections = new List<BackendServiceConnection>();
        private readonly CancellationTokenSource stopping = new CancellationTokenSource();
        private TextWriter log;
        private BackendServiceConnection owner;
        private NativeBackendJob backend;
        private CancellationTokenSource startupCancellation;
        private Task startupWork;
        private string startupStatus;
        private bool backendReady;
        private bool backendAdopted;
        private bool backendOwned;
        private bool backendStopping;
        private bool stopScheduled;
        private int backendTerminationExitCode;

        private BackendService(LauncherPaths paths)
        {
            this.paths = paths;
            ServiceName = ServiceRegistration.ServiceName(paths.RootDirectory);
            AutoLog = false;
            CanStop = true;
            CanShutdown = true;
            CanPauseAndContinue = false;
        }

        public static bool IsCommand(string[] args)
        {
            return args != null && args.Length >= 1 && string.Equals(args[0], ServiceRegistration.ServiceArgument, StringComparison.Ordinal);
        }

        public static int Run(LauncherPaths paths, string[] args)
        {
            if (args.Length != 1)
            {
                return 2;
            }
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            {
                if (!identity.IsSystem)
                {
                    return 1;
                }
            }
            using (BackendService service = new BackendService(paths))
            {
                System.ServiceProcess.ServiceBase.Run(service);
            }
            return 0;
        }

        protected override void OnStart(string[] args)
        {
            if (args != null && args.Length != 0)
            {
                ExitCode = 87;
                throw new ArgumentException("The SoAI service does not accept start parameters.");
            }
            string logPath = LauncherDiagnostics.ServiceLogPath(paths);
            Directory.CreateDirectory(Path.GetDirectoryName(logPath));
            StreamWriter logWriter = new StreamWriter(new FileStream(logPath, FileMode.Append, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete), new UTF8Encoding(false));
            logWriter.AutoFlush = true;
            log = TextWriter.Synchronized(logWriter);
            Console.SetOut(log);
            Console.SetError(log);
            Log("The SoAI service started for " + paths.RootDirectory + ".");
            NamedPipeServerStream firstPipe = CreatePipe(true);
            Task.Run(new Func<Task>(delegate { return ListenAsync(firstPipe); }));
            Task.Run(new Func<Task>(SuperviseAsync));
            lock (sync)
            {
                BeginStartup();
            }
        }

        protected override void OnStop()
        {
            Shutdown(BackendStopTimeout);
        }

        protected override void OnShutdown()
        {
            Shutdown(SystemShutdownStopTimeout);
        }

        private void Log(string message)
        {
            TextWriter writer = log;
            if (writer != null)
            {
                writer.WriteLine(DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture) + " " + message);
            }
        }

        private NamedPipeServerStream CreatePipe(bool firstInstance)
        {
            using (NativeSecurityDescriptor descriptor = new NativeSecurityDescriptor(PipeSecurity))
            {
                PIPE_SECURITY_ATTRIBUTES attributes = new PIPE_SECURITY_ATTRIBUTES();
                attributes.Length = Marshal.SizeOf(typeof(PIPE_SECURITY_ATTRIBUTES));
                attributes.SecurityDescriptor = descriptor.Handle;
                SafePipeHandle handle = CreateNamedPipe(
                    "\\\\.\\pipe\\" + ServiceRegistration.PipeName(paths),
                    PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED | (firstInstance ? FILE_FLAG_FIRST_PIPE_INSTANCE : 0),
                    PIPE_REJECT_REMOTE_CLIENTS,
                    PIPE_UNLIMITED_INSTANCES,
                    4096,
                    4096,
                    0,
                    ref attributes);
                if (handle.IsInvalid)
                {
                    int error = Marshal.GetLastWin32Error();
                    handle.Dispose();
                    throw new Win32Exception(error, firstInstance
                        ? "Another process already owns the SoAI service channel."
                        : "The SoAI service channel could not accept another window.");
                }
                return new NamedPipeServerStream(PipeDirection.InOut, true, false, handle);
            }
        }

        private async Task ListenAsync(NamedPipeServerStream pipe)
        {
            while (true)
            {
                try
                {
                    await pipe.WaitForConnectionAsync(stopping.Token);
                }
                catch (OperationCanceledException)
                {
                    pipe.Dispose();
                    return;
                }
                catch (IOException exception)
                {
                    pipe.Dispose();
                    if (stopping.IsCancellationRequested)
                    {
                        return;
                    }
                    Log("A SoAI window connection failed: " + exception.Message);
                    pipe = null;
                }
                if (pipe != null)
                {
                    Accept(new BackendServiceConnection(pipe));
                }
                try
                {
                    pipe = CreatePipe(false);
                }
                catch (Exception exception)
                {
                    Log("The SoAI service stopped accepting windows: " + exception);
                    ExitCode = 1;
                    ScheduleStop();
                    return;
                }
            }
        }

        private void Accept(BackendServiceConnection connection)
        {
            lock (sync)
            {
                if (stopScheduled)
                {
                    connection.Close();
                    return;
                }
                connections.Add(connection);
                if (backendReady)
                {
                    connection.Send("READY");
                }
                else
                {
                    BeginStartup();
                    connection.Send("STATUS\t" + (startupStatus ?? "Waiting for SoAI to stop..."));
                }
            }
            Task.Run(new Func<Task>(delegate { return ServeAsync(connection); }));
        }

        private async Task ServeAsync(BackendServiceConnection connection)
        {
            string ending = null;
            try
            {
                while (true)
                {
                    string message = await connection.ReadMessageAsync();
                    if (!string.Equals(message, "COMMIT", StringComparison.Ordinal))
                    {
                        ending = message;
                        break;
                    }
                    lock (sync)
                    {
                        if (!connection.ReadySent || connection.Committed || !backendReady)
                        {
                            break;
                        }
                        connection.Committed = true;
                        if (owner == null)
                        {
                            owner = connection;
                            backendOwned = true;
                        }
                    }
                    connection.Send("COMMITTED");
                }
            }
            catch (IOException)
            {
            }
            catch (ObjectDisposedException)
            {
            }
            catch (InvalidDataException exception)
            {
                Log(exception.Message);
            }
            EndConnection(connection, ending);
        }

        private void EndConnection(BackendServiceConnection connection, string ending)
        {
            bool stopBackend = false;
            NativeBackendJob job = null;
            CancellationTokenSource abandonedStartup = null;
            lock (sync)
            {
                if (!connections.Remove(connection))
                {
                    return;
                }
                bool released = string.Equals(ending, "RELEASE", StringComparison.Ordinal);
                if (ReferenceEquals(owner, connection))
                {
                    owner = null;
                    stopBackend = !released;
                }
                else if (owner == null && connections.Count == 0 && !released)
                {
                    if (startupStatus != null)
                    {
                        abandonedStartup = startupCancellation;
                    }
                    else
                    {
                        stopBackend = backendReady && backend != null && !backendOwned;
                    }
                }
                if (stopBackend)
                {
                    backendStopping = true;
                    backendReady = false;
                    job = backend;
                    if (job != null) { job.Commit(); }
                    backend = null;
                }
            }
            connection.Close();
            if (abandonedStartup != null)
            {
                abandonedStartup.Cancel();
            }
            if (stopBackend)
            {
                Stopwatch stopClock = Stopwatch.StartNew();
                TimeSpan remaining;
                try { remaining = ServiceRegistration.ReadStopTimeout(paths.RootDirectory, BackendStopTimeout); }
                catch (Exception exception)
                {
                    Log("The public stop deadline could not be verified: " + exception);
                    remaining = TimeSpan.Zero;
                }
                bool completed = StopBackend(remaining - stopClock.Elapsed);
                if (job != null)
                {
                    completed = completed && WaitForBackendExit(job, remaining - stopClock.Elapsed);
                    if (job.HasExited && job.ExitCode != 0) { completed = false; }
                    if (completed) { DisposeQuietly(job); }
                }
                lock (sync)
                {
                    backendStopping = false;
                    backendTerminationExitCode = completed ? 0 : 1460;
                    if (completed)
                    {
                        backendAdopted = false;
                        ResumeWaitingStartup();
                    }
                    else
                    {
                        backend = job;
                        Log("SoAI shutdown is incomplete; backend ownership and recovery evidence were retained.");
                    }
                }
            }
            EvaluateLifetime();
        }

        private void ResumeWaitingStartup()
        {
            foreach (BackendServiceConnection connection in connections)
            {
                if (!connection.ReadySent)
                {
                    BeginStartup();
                    return;
                }
            }
        }

        private void BeginStartup()
        {
            if (stopScheduled || startupStatus != null || backendReady || backendStopping || backend != null)
            {
                return;
            }
            startupStatus = "Preparing SoAI...";
            startupCancellation = new CancellationTokenSource();
            CancellationToken token = startupCancellation.Token;
            startupWork = Task.Run(new Func<Task>(delegate { return StartBackendAsync(token); }));
        }

        private void UpdateStatus(string status)
        {
            lock (sync)
            {
                if (startupStatus == null || string.Equals(startupStatus, status, StringComparison.Ordinal))
                {
                    return;
                }
                startupStatus = status;
                foreach (BackendServiceConnection connection in connections)
                {
                    if (!connection.ReadySent)
                    {
                        connection.Send("STATUS\t" + status);
                    }
                }
            }
        }

        private async Task StartBackendAsync(CancellationToken token)
        {
            try
            {
                EndpointInfo existing = await DiscoveryProbe.WaitForEndpointAsync(TimeSpan.FromMilliseconds(250), TimeSpan.FromSeconds(2), CancellationToken.None);
                if (existing != null && await HealthProbe.WaitForReadyAsync(existing, TimeSpan.FromMilliseconds(250), TimeSpan.FromSeconds(2), CancellationToken.None))
                {
                    SecureInstallation(true);
                    Log("Using the SoAI instance that is already running.");
                    CompleteStartup(null);
                    return;
                }
                string restoration = UpdateRecovery.InspectRequiredRestoration(paths);
                if (restoration != null)
                {
                    RequireRestoration(restoration);
                    return;
                }
                SecureInstallation(false);
                if (token.IsCancellationRequested)
                {
                    FailStartup("SoAI startup was cancelled.");
                    return;
                }
                UpdateStatus("Starting SoAI...");
                NativeBackendJob job = NativeBackendJob.Start(paths, BackendArguments);
                lock (sync)
                {
                    backend = job;
                    backendOwned = false;
                    if (stopScheduled)
                    {
                        job.Commit();
                        return;
                    }
                }
                Log("Started the SoAI backend process " + job.ProcessHandle.Id.ToString(CultureInfo.InvariantCulture) + ".");
                Stopwatch readinessClock = Stopwatch.StartNew();
                NativeImageAllowance readiness = await Task.Run(delegate { return paths.ManagedRuntimeReadinessAllowance(BackendStartupTimeout); });
                Log("Backend readiness allowance is " + readiness.WholeSeconds.ToString(CultureInfo.InvariantCulture) + " seconds for " + readiness.ImageCount.ToString(CultureInfo.InvariantCulture) + " managed native image candidates" + (readiness.InventoryComplete ? "." : "; the image inventory was incomplete."));
                while (readinessClock.Elapsed < readiness.Duration)
                {
                    if (token.IsCancellationRequested)
                    {
                        FailStartup("SoAI startup was cancelled.");
                        return;
                    }
                    if (job.HasExited)
                    {
                        WriteBackendExitFailure(job.ExitCode);
                        FailStartup("SoAI stopped before it became ready with backend exit code " + job.ExitCode.ToString(CultureInfo.InvariantCulture) + ". " + DiagnosticsLocation);
                        return;
                    }
                    EndpointInfo endpoint = await DiscoveryProbe.TryResolveAsync(CancellationToken.None);
                    if (endpoint != null && await HealthProbe.IsReadyAsync(endpoint, CancellationToken.None))
                    {
                        SecureInstallation(true);
                        CompleteStartup(job);
                        return;
                    }
                    UpdateStatus("Waiting for SoAI to become ready...");
                    await Task.Delay(500);
                }
                FailStartup(readiness.DescribeTimeout("SoAI") + " " + DiagnosticsLocation);
            }
            catch (InstallationSecurityRequiredException exception)
            {
                Log("SoAI startup failed: " + exception);
                FailStartup(exception.Message + " " + DiagnosticsLocation);
            }
            catch (Exception exception)
            {
                Log("SoAI startup failed: " + exception);
                FailStartup("SoAI could not start. " + DiagnosticsLocation);
            }
        }

        private void SecureInstallation(bool requireCompletion)
        {
            if (InstallationSecurity.IsSecured(paths.RootDirectory))
            {
                return;
            }
            UpdateStatus("Securing SoAI files...");
            Log("Securing the SoAI installation folder.");
            int securityExitCode = BackendProcess.SecureInstallation(paths, false);
            if (securityExitCode != 0)
            {
                throw new InvalidOperationException("Securing the SoAI installation folder failed with exit code " + securityExitCode.ToString(CultureInfo.InvariantCulture) + ".");
            }
            if (requireCompletion && !InstallationSecurity.IsSecured(paths.RootDirectory))
            {
                throw new InstallationSecurityRequiredException();
            }
        }

        private void CompleteStartup(NativeBackendJob job)
        {
            lock (sync)
            {
                startupStatus = null;
                startupCancellation = null;
                backendReady = true;
                backendAdopted = job == null;
                backendTerminationExitCode = 0;
                foreach (BackendServiceConnection connection in connections)
                {
                    if (!connection.ReadySent)
                    {
                        connection.Send("READY");
                    }
                }
            }
            Log("SoAI is ready.");
            EvaluateLifetime();
        }

        private void FailStartup(string message)
        {
            NativeBackendJob job;
            List<BackendServiceConnection> waiting = new List<BackendServiceConnection>();
            lock (sync)
            {
                if (stopScheduled) { return; }
                job = backend;
                backend = null;
                startupStatus = null;
                startupCancellation = null;
                backendReady = false;
                foreach (BackendServiceConnection connection in connections)
                {
                    if (!connection.ReadySent)
                    {
                        connection.Send("ERROR\t" + message);
                        waiting.Add(connection);
                    }
                }
                foreach (BackendServiceConnection connection in waiting)
                {
                    connections.Remove(connection);
                }
            }
            foreach (BackendServiceConnection connection in waiting)
            {
                connection.Close();
            }
            Log(message);
            if (job != null)
            {
                DisposeQuietly(job);
            }
            EvaluateLifetime();
        }

        private void RequireRestoration(string transactionPath)
        {
            BackendServiceConnection[] waiting;
            lock (sync)
            {
                startupStatus = null;
                startupCancellation = null;
                waiting = connections.ToArray();
                connections.Clear();
                foreach (BackendServiceConnection connection in waiting)
                {
                    if (!connection.ReadySent)
                    {
                        connection.Send("RESTORE\t" + transactionPath);
                    }
                }
            }
            foreach (BackendServiceConnection connection in waiting)
            {
                connection.Close();
            }
            Log("The interrupted update in " + transactionPath + " requires restoration; the service is stopping.");
            ScheduleStop();
        }

        private async Task SuperviseAsync()
        {
            while (true)
            {
                try
                {
                    await Task.Delay(SupervisionInterval, stopping.Token);
                }
                catch (OperationCanceledException)
                {
                    return;
                }
                NativeBackendJob finished = null;
                lock (sync)
                {
                    if (backend != null && startupStatus == null && !backend.HasActiveProcesses())
                    {
                        finished = backend;
                        backendTerminationExitCode = finished.HasExited ? finished.ExitCode : -1;
                        backend = null;
                        backendReady = false;
                        owner = null;
                        ResumeWaitingStartup();
                    }
                }
                if (finished != null)
                {
                    Log("The SoAI backend has no remaining processes.");
                    DisposeQuietly(finished);
                }
                EvaluateLifetime();
            }
        }

        private void EvaluateLifetime()
        {
            lock (sync)
            {
                if (stopScheduled || startupStatus != null || backendStopping || backend != null || connections.Count > 0)
                {
                    return;
                }
            }
            Log("No SoAI window or backend remains; the service is stopping.");
            ScheduleStop();
        }

        private void ScheduleStop()
        {
            lock (sync)
            {
                if (stopScheduled)
                {
                    return;
                }
                stopScheduled = true;
            }
            ThreadPool.QueueUserWorkItem(delegate { Stop(); });
        }

        private bool StopBackend(TimeSpan timeout)
        {
            Stopwatch controlClock = Stopwatch.StartNew();
            Log("Stopping SoAI.");
            if (timeout <= TimeSpan.Zero) { Log("The public stop deadline was exhausted before service control. Recovery evidence was retained."); return false; }
            try
            {
                using (NativeBackendJob command = NativeBackendJob.StartServiceStop(paths, timeout))
                {
                    try
                    {
                        if (!command.ProcessHandle.WaitForExit((int)Math.Max(0, (timeout - controlClock.Elapsed).TotalMilliseconds)))
                        {
                            Log("The SoAI stop control exceeded its deadline. Recovery evidence was retained.");
                            return false;
                        }
                        return command.ExitCode == 0;
                    }
                    finally { command.CancelControl(); }
                }
            }
            catch (Exception exception)
            {
                Log("The SoAI stop command failed: " + exception);
                return false;
            }
        }

        private void Shutdown(TimeSpan stopTimeout)
        {
            Stopwatch stopClock = Stopwatch.StartNew();
            try { stopTimeout = ServiceRegistration.ReadStopTimeout(paths.RootDirectory, stopTimeout); }
            catch (Exception exception)
            {
                Log("The public stop deadline could not be verified: " + exception);
                stopTimeout = TimeSpan.Zero;
            }
            RequestAdditionalTime(Math.Max(1, (int)stopTimeout.TotalMilliseconds));
            NativeBackendJob job;
            bool running;
            BackendServiceConnection[] open;
            CancellationTokenSource startup;
            Task pendingStartup;
            lock (sync)
            {
                bool stoppedByWindowsOrOwner = !stopScheduled || owner != null;
                stopScheduled = true;
                job = backend;
                if (job != null) { job.Commit(); }
                backend = null;
                running = !backendStopping && ((backendAdopted && stoppedByWindowsOrOwner) || (job != null && job.HasActiveProcesses()));
                startup = startupCancellation;
                pendingStartup = startupWork;
                open = connections.ToArray();
                connections.Clear();
                owner = null;
                startupStatus = null;
                startupCancellation = null;
                backendReady = false;
                backendAdopted = false;
            }
            stopping.Cancel();
            if (startup != null) { startup.Cancel(); }
            foreach (BackendServiceConnection connection in open) { connection.Close(); }
            bool startupSettled = pendingStartup == null || pendingStartup.IsCompleted;
            if (!startupSettled)
            {
                try { startupSettled = pendingStartup.Wait((int)Math.Max(0, (stopTimeout - stopClock.Elapsed).TotalMilliseconds)); }
                catch (AggregateException) { startupSettled = pendingStartup.IsCanceled; }
            }
            if (pendingStartup != null && pendingStartup.IsFaulted)
            {
                Log("Startup failed during shutdown: " + pendingStartup.Exception);
                startupSettled = false;
            }
            lock (sync)
            {
                if (job == null && backend != null)
                {
                    job = backend;
                    job.Commit();
                    backend = null;
                    running = job.HasActiveProcesses();
                }
            }
            bool completed = (!running || StopBackend(stopTimeout - stopClock.Elapsed)) && startupSettled;
            if (job != null && job.HasExited && job.ExitCode != 0) { completed = false; }
            if (job != null)
            {
                completed = WaitForBackendExit(job, stopTimeout - stopClock.Elapsed) && completed;
                if (!completed) { job.Commit(); }
                DisposeQuietly(job);
            }
            while (stopClock.Elapsed < stopTimeout)
            {
                lock (sync) { if (!backendStopping) { break; } }
                Thread.Sleep(25);
            }
            lock (sync) { completed = completed && !backendStopping && backendTerminationExitCode == 0; }
            if (!completed)
            {
                ExitCode = 1460;
                Log("The SoAI service shutdown is incomplete. Backend finalizers and recovery evidence were retained.");
                return;
            }
            Log("The SoAI service stopped.");
        }

        private static bool WaitForBackendExit(NativeBackendJob job, TimeSpan remaining)
        {
            Stopwatch elapsed = Stopwatch.StartNew();
            while (job.HasActiveProcesses())
            {
                if (elapsed.Elapsed >= remaining) { return false; }
                Thread.Sleep(25);
            }
            return true;
        }

        private void DisposeQuietly(NativeBackendJob job)
        {
            try
            {
                job.Dispose();
            }
            catch (Exception exception)
            {
                Log("SoAI backend processes could not be stopped: " + exception);
            }
        }

        private void WriteBackendExitFailure(int exitCode)
        {
            string backendLogPath = Path.Combine(paths.RootDirectory, "data", "logs", "soai-launcher.log");
            Log("The SoAI backend exited with code " + exitCode.ToString(CultureInfo.InvariantCulture) + " before it became ready. Recent output from " + backendLogPath + ":" + Environment.NewLine + LauncherDiagnostics.ReadLogTail(backendLogPath));
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct PIPE_SECURITY_ATTRIBUTES
        {
            public int Length;
            public IntPtr SecurityDescriptor;
            public bool InheritHandle;
        }

        [DllImport("kernel32.dll", EntryPoint = "CreateNamedPipeW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern SafePipeHandle CreateNamedPipe(string name, uint openMode, uint pipeMode, uint maximumInstances, uint outBufferSize, uint inBufferSize, uint defaultTimeout, ref PIPE_SECURITY_ATTRIBUTES securityAttributes);
    }

    public static class ServiceRegistration
    {
        public const string ServiceArgument = "--soai-backend-service";
        private const string RegisterArgument = "--soai-register-service";
        private const string UnregisterArgument = "--soai-unregister-service";
        private const string ServiceSecurity = "D:(A;;CCLCSWRPWPDTLOCRRC;;;SY)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)(A;;CCLCSWLOCRRC;;;IU)(A;;CCLCSWLOCRRC;;;SU)(A;;RPLCLO;;;IU)";
        private const string LocalSystemAccount = "LocalSystem";
        private const string RepairMessage = "The SoAI background service is missing or damaged. Repair SoAI by running SoAI Setup again, or by reinstalling it from the complete archive.";
        private const uint SC_MANAGER_CONNECT = 0x0001;
        private const uint SC_MANAGER_CREATE_SERVICE = 0x0002;
        private const uint SERVICE_QUERY_CONFIG = 0x0001;
        private const uint SERVICE_CHANGE_CONFIG = 0x0002;
        private const uint SERVICE_QUERY_STATUS = 0x0004;
        private const uint SERVICE_START = 0x0010;
        private const uint SERVICE_STOP = 0x0020;
        private const uint DELETE = 0x00010000;
        private const uint READ_CONTROL = 0x00020000;
        private const uint WRITE_DAC = 0x00040000;
        private const uint SERVICE_WIN32_OWN_PROCESS = 0x00000010;
        private const uint SERVICE_DEMAND_START = 0x00000003;
        private const uint SERVICE_ERROR_NORMAL = 0x00000001;
        private const uint SERVICE_CONTROL_STOP = 0x00000001;
        private const uint SERVICE_STOPPED = 0x00000001;
        private const uint SERVICE_STOP_PENDING = 0x00000003;
        private const uint SERVICE_RUNNING = 0x00000004;
        private const uint SERVICE_CONFIG_DESCRIPTION = 1;
        private const uint SERVICE_CONFIG_FAILURE_ACTIONS = 2;
        private const uint DACL_SECURITY_INFORMATION = 0x00000004;
        private const int SC_STATUS_PROCESS_INFO = 0;
        private const int ERROR_INSUFFICIENT_BUFFER = 122;
        private const int ERROR_SERVICE_ALREADY_RUNNING = 1056;
        private const int ERROR_SERVICE_DISABLED = 1058;
        private const int ERROR_SERVICE_DOES_NOT_EXIST = 1060;
        private const int ERROR_SERVICE_CANNOT_ACCEPT_CTRL = 1061;
        private const int ERROR_SERVICE_NOT_ACTIVE = 1062;
        private const int ERROR_SERVICE_MARKED_FOR_DELETE = 1072;
        private static readonly TimeSpan RegistrationStopTimeout = TimeSpan.FromMinutes(5);

        private static string StopDeadlineKey(string root)
        {
            return "Software\\SoAI.Lifecycle\\Stop\\" + LauncherPaths.StableRootIdentity(root);
        }

        internal static void PublishStopDeadline(LauncherPaths paths, double expires)
        {
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT))
            using (ServiceHandle service = OpenServiceHandle(manager, ServiceName(paths.RootDirectory), SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS))
            {
                if (service.IsInvalid)
                {
                    int failure = Marshal.GetLastWin32Error();
                    if (failure == ERROR_SERVICE_DOES_NOT_EXIST) { return; }
                    throw new Win32Exception(failure, "The SoAI service stop deadline could not be published.");
                }
                RequireRegisteredConfiguration(service, paths);
                SERVICE_STATUS_PROCESS status = QueryStatus(service);
                if (status.CurrentState == SERVICE_STOPPED) { return; }
                if (status.CurrentState == SERVICE_STOP_PENDING) { return; }
                using (Process process = Process.GetProcessById(status.ProcessId))
                {
                    if (!string.Equals(NativeBackendJob.ReadProcessImagePath(process.Handle), Path.Combine(paths.RootDirectory, "soai.exe"), StringComparison.OrdinalIgnoreCase))
                    {
                        throw new InvalidOperationException("The SoAI service process identity changed before its stop deadline could be published. Retry stop after verifying the service.");
                    }
                    long created = process.StartTime.ToUniversalTime().ToFileTimeUtc();
                    if (process.HasExited) { return; }
                    byte[] record = new byte[20];
                    Buffer.BlockCopy(BitConverter.GetBytes(expires), 0, record, 0, 8);
                    Buffer.BlockCopy(BitConverter.GetBytes(process.Id), 0, record, 8, 4);
                    Buffer.BlockCopy(BitConverter.GetBytes(created), 0, record, 12, 8);
                    using (RegistryKey machine = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
                    using (RegistryKey publication = machine.CreateSubKey(StopDeadlineKey(paths.RootDirectory)))
                    {
                        publication.SetValue("CompletionDeadline", record, RegistryValueKind.Binary);
                        publication.Flush();
                    }
                }
            }
        }

        internal static TimeSpan ReadStopTimeout(string root, TimeSpan requested)
        {
            using (RegistryKey machine = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
            using (RegistryKey publication = machine.OpenSubKey(StopDeadlineKey(root)))
            {
                if (publication == null) { return requested; }
                byte[] record = publication.GetValue("CompletionDeadline") as byte[];
                if (record == null || record.Length != 20) { throw new InvalidOperationException("The public stop deadline record is invalid."); }
                using (Process current = Process.GetCurrentProcess())
                {
                    if (BitConverter.ToInt32(record, 8) != current.Id
                        || BitConverter.ToInt64(record, 12) != current.StartTime.ToUniversalTime().ToFileTimeUtc()) { return requested; }
                }
                double expires = BitConverter.ToDouble(record, 0);
                double now = (double)Stopwatch.GetTimestamp() / Stopwatch.Frequency;
                if (double.IsNaN(expires) || double.IsInfinity(expires) || expires > now + 150)
                {
                    throw new InvalidOperationException("The public stop deadline record is invalid.");
                }
                return TimeSpan.FromSeconds(Math.Max(0, Math.Min(requested.TotalSeconds, expires - now)));
            }
        }

        internal static void ClearStopDeadline(string root, double? expectedDeadline)
        {
            Mutex ownership = null;
            try
            {
                if (!expectedDeadline.HasValue)
                {
                    bool created;
                    ownership = new Mutex(false, "Global\\SoAI.PublicStop." + LauncherPaths.StableRootIdentity(root), out created);
                    if (!created) { throw new InvalidOperationException("A public SoAI stop operation still owns this installation. Wait for its result before completing uninstall."); }
                }
                using (RegistryKey machine = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
                {
                    bool empty;
                    using (RegistryKey publication = machine.OpenSubKey(StopDeadlineKey(root), true))
                    {
                        if (publication == null) { return; }
                        byte[] record = publication.GetValue("CompletionDeadline") as byte[];
                        if (expectedDeadline.HasValue && (record == null || record.Length != 20 || BitConverter.ToDouble(record, 0) != expectedDeadline.Value)) { return; }
                        publication.DeleteValue("CompletionDeadline", false);
                        publication.Flush();
                        empty = publication.SubKeyCount == 0 && publication.ValueCount == 0;
                    }
                    if (empty) { machine.DeleteSubKey(StopDeadlineKey(root), false); }
                }
            }
            finally { if (ownership != null) { ownership.Dispose(); } }
        }

        internal static void RequireSuccessfulStop(string root)
        {
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT))
            using (ServiceHandle service = OpenServiceHandle(manager, ServiceName(root), SERVICE_QUERY_STATUS))
            {
                if (service.IsInvalid)
                {
                    int failure = Marshal.GetLastWin32Error();
                    if (failure == ERROR_SERVICE_DOES_NOT_EXIST) { return; }
                    throw new Win32Exception(failure, "The SoAI service stop result could not be inspected.");
                }
                SERVICE_STATUS_PROCESS status = QueryStatus(service);
                if (status.CurrentState != SERVICE_STOPPED || status.Win32ExitCode != 0 || status.ServiceSpecificExitCode != 0)
                {
                    throw new InvalidOperationException("The SoAI service did not verify clean shutdown. Its recovery evidence was retained; inspect soai-service.log before retrying.");
                }
            }
        }

        public static string ServiceName(string rootDirectory)
        {
            return "SoAI-" + LauncherPaths.StableRootIdentity(rootDirectory);
        }

        internal static string PipeName(LauncherPaths paths)
        {
            return "SoAI-Service-" + LauncherPaths.StableRootIdentity(paths.RootDirectory);
        }

        private static string DisplayName(LauncherPaths paths)
        {
            return "SoAI (" + LauncherPaths.StableRootIdentity(paths.RootDirectory) + ")";
        }

        private static string ImagePath(LauncherPaths paths)
        {
            return BackendProcess.Quote(Path.Combine(paths.RootDirectory, "soai.exe")) + " " + ServiceArgument;
        }

        public static bool IsCommand(string[] args)
        {
            return args != null && args.Length >= 1
                && (string.Equals(args[0], RegisterArgument, StringComparison.Ordinal)
                    || string.Equals(args[0], UnregisterArgument, StringComparison.Ordinal));
        }

        public static int Run(string[] args)
        {
            NativeConsole.UseStrictUtf8StandardStreams();
            try
            {
                if (args.Length != 2 || !LauncherPaths.IsAbsoluteFilesystemPath(args[1]))
                {
                    throw new ArgumentException("SoAI service registration requires one absolute installation directory.");
                }
                if (!PrivilegeState.IsElevated())
                {
                    throw new InvalidOperationException("SoAI service registration requires administrator access.");
                }
                if (string.Equals(args[0], RegisterArgument, StringComparison.Ordinal))
                {
                    Console.WriteLine(Register(args[1]) ? "created" : "updated");
                }
                else
                {
                    Console.WriteLine(Unregister(args[1]) ? "removed" : "absent");
                }
                return 0;
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine("SoAI service registration failed: " + exception.Message);
                return 1;
            }
        }

        public static bool Register(string rootDirectory)
        {
            LauncherPaths paths = LauncherPaths.FromRoot(rootDirectory);
            string executable = Path.Combine(paths.RootDirectory, "soai.exe");
            if (!File.Exists(LauncherPaths.ToNativeFilesystemPath(executable)))
            {
                throw new FileNotFoundException("The SoAI launcher is missing from the installation directory.", executable);
            }
            string name = ServiceName(paths.RootDirectory);
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT | SC_MANAGER_CREATE_SERVICE))
            {
                bool created = false;
                ServiceHandle service = OpenServiceHandle(manager, name, SERVICE_CHANGE_CONFIG | SERVICE_QUERY_CONFIG | READ_CONTROL | WRITE_DAC);
                try
                {
                    if (service.IsInvalid)
                    {
                        int error = Marshal.GetLastWin32Error();
                        if (error != ERROR_SERVICE_DOES_NOT_EXIST)
                        {
                            throw new Win32Exception(error, "Windows could not open the SoAI service registration.");
                        }
                        service.Dispose();
                        service = CreateServiceHandle(
                            manager, name, DisplayName(paths), SERVICE_CHANGE_CONFIG | SERVICE_QUERY_CONFIG | READ_CONTROL | WRITE_DAC | DELETE,
                            SERVICE_WIN32_OWN_PROCESS, SERVICE_DEMAND_START, SERVICE_ERROR_NORMAL, ImagePath(paths),
                            null, IntPtr.Zero, "\0", LocalSystemAccount, null);
                        if (service.IsInvalid)
                        {
                            int createError = Marshal.GetLastWin32Error();
                            throw new Win32Exception(createError, createError == ERROR_SERVICE_MARKED_FOR_DELETE
                                ? "A previous SoAI service is still being removed. Restart Windows, then run SoAI Setup again."
                                : "Windows could not create the SoAI service.");
                        }
                        created = true;
                    }
                    else if (!ChangeServiceConfig(
                        service, SERVICE_WIN32_OWN_PROCESS, SERVICE_DEMAND_START, SERVICE_ERROR_NORMAL, ImagePath(paths),
                        null, IntPtr.Zero, "\0", LocalSystemAccount, string.Empty, DisplayName(paths)))
                    {
                        int changeError = Marshal.GetLastWin32Error();
                        throw new Win32Exception(changeError, changeError == ERROR_SERVICE_MARKED_FOR_DELETE
                            ? "A previous SoAI service is still being removed. Restart Windows, then run SoAI Setup again."
                            : "Windows could not update the SoAI service.");
                    }
                    ConfigureService(service, paths);
                    return created;
                }
                catch
                {
                    if (created)
                    {
                        DeleteService(service);
                    }
                    throw;
                }
                finally
                {
                    service.Dispose();
                }
            }
        }

        private static void ConfigureService(ServiceHandle service, LauncherPaths paths)
        {
            SERVICE_DESCRIPTION description = new SERVICE_DESCRIPTION();
            description.Description = "Runs the SoAI backend installed in " + paths.RootDirectory + ".";
            if (!ChangeServiceDescription(service, SERVICE_CONFIG_DESCRIPTION, ref description))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not describe the SoAI service.");
            }
            IntPtr action = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(SC_ACTION)));
            try
            {
                Marshal.StructureToPtr(new SC_ACTION(), action, false);
                SERVICE_FAILURE_ACTIONS failureActions = new SERVICE_FAILURE_ACTIONS();
                failureActions.Actions = action;
                if (!ChangeServiceFailureActions(service, SERVICE_CONFIG_FAILURE_ACTIONS, ref failureActions))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not clear the SoAI service recovery actions.");
                }
            }
            finally
            {
                Marshal.FreeHGlobal(action);
            }
            using (NativeSecurityDescriptor descriptor = new NativeSecurityDescriptor(ServiceSecurity))
            {
                if (!SetServiceObjectSecurity(service, DACL_SECURITY_INFORMATION, descriptor.Handle))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not apply the SoAI service permissions.");
                }
            }
        }

        public static bool Unregister(string rootDirectory)
        {
            string name = ServiceName(LauncherPaths.FromRoot(rootDirectory).RootDirectory);
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT))
            using (ServiceHandle service = OpenServiceHandle(manager, name, SERVICE_STOP | SERVICE_QUERY_STATUS | DELETE))
            {
                if (service.IsInvalid)
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error == ERROR_SERVICE_DOES_NOT_EXIST)
                    {
                        return false;
                    }
                    throw new Win32Exception(error, "Windows could not open the SoAI service registration.");
                }
                if (!StopAndWait(service, RegistrationStopTimeout))
                {
                    throw new TimeoutException("The SoAI service did not stop within 5 minutes.");
                }
                if (!DeleteService(service))
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error != ERROR_SERVICE_MARKED_FOR_DELETE)
                    {
                        throw new Win32Exception(error, "Windows could not remove the SoAI service.");
                    }
                }
                return true;
            }
        }

        public static bool Stop(string rootDirectory, int timeoutSeconds)
        {
            return Stop(rootDirectory, TimeSpan.FromSeconds(timeoutSeconds));
        }

        internal static bool Stop(string rootDirectory, TimeSpan timeout)
        {
            LauncherPaths paths = LauncherPaths.FromRoot(rootDirectory);
            string name = ServiceName(paths.RootDirectory);
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT))
            using (ServiceHandle service = OpenServiceHandle(manager, name, SERVICE_STOP | SERVICE_QUERY_STATUS | SERVICE_QUERY_CONFIG))
            {
                if (service.IsInvalid)
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error == ERROR_SERVICE_DOES_NOT_EXIST)
                    {
                        return true;
                    }
                    throw new Win32Exception(error, "Windows could not open the SoAI service.");
                }
                RequireRegisteredConfiguration(service, paths);
                return StopAndWait(service, timeout);
            }
        }

        public static void Start(string rootDirectory)
        {
            string name = ServiceName(LauncherPaths.FromRoot(rootDirectory).RootDirectory);
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT))
            using (ServiceHandle service = OpenServiceHandle(manager, name, SERVICE_START))
            {
                if (service.IsInvalid)
                {
                    throw new InvalidOperationException(RepairMessage, new Win32Exception(Marshal.GetLastWin32Error()));
                }
                if (!StartService(service, 0, IntPtr.Zero))
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error != ERROR_SERVICE_ALREADY_RUNNING)
                    {
                        throw new Win32Exception(error, "Windows could not start the SoAI background service.");
                    }
                }
            }
        }

        public static bool WaitForStopped(string rootDirectory, TimeSpan timeout)
        {
            string name = ServiceName(rootDirectory);
            Stopwatch elapsed = Stopwatch.StartNew();
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT))
            using (ServiceHandle service = OpenServiceHandle(manager, name, SERVICE_QUERY_STATUS))
            {
                if (service.IsInvalid)
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error == ERROR_SERVICE_DOES_NOT_EXIST)
                    {
                        return true;
                    }
                    throw new Win32Exception(error, "Windows could not open the SoAI service.");
                }
                while (QueryStatus(service).CurrentState != SERVICE_STOPPED)
                {
                    if (elapsed.Elapsed >= timeout)
                    {
                        return false;
                    }
                    Thread.Sleep(250);
                }
                return true;
            }
        }

        internal static int EnsureRunning(LauncherPaths paths, ref bool startRequested)
        {
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT))
            using (ServiceHandle service = OpenServiceHandle(manager, ServiceName(paths.RootDirectory), SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS | SERVICE_START))
            {
                if (service.IsInvalid)
                {
                    int error = Marshal.GetLastWin32Error();
                    throw new InvalidOperationException(RepairMessage, new Win32Exception(error));
                }
                RequireRegisteredConfiguration(service, paths);
                SERVICE_STATUS_PROCESS status = QueryStatus(service);
                if (status.CurrentState == SERVICE_RUNNING)
                {
                    return status.ProcessId;
                }
                if (status.CurrentState != SERVICE_STOPPED)
                {
                    return 0;
                }
                if (startRequested && (status.Win32ExitCode != 0 || status.ServiceSpecificExitCode != 0))
                {
                    throw new InvalidOperationException("The SoAI background service stopped with error " + status.Win32ExitCode.ToString(CultureInfo.InvariantCulture) + ". Service diagnostics are in soai-service.log in the SoAI data\\logs folder.");
                }
                if (!StartService(service, 0, IntPtr.Zero))
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error == ERROR_SERVICE_DISABLED)
                    {
                        throw new InvalidOperationException(RepairMessage, new Win32Exception(error));
                    }
                    if (error != ERROR_SERVICE_ALREADY_RUNNING)
                    {
                        throw new Win32Exception(error, "Windows could not start the SoAI background service.");
                    }
                }
                startRequested = true;
                return 0;
            }
        }

        internal static int QueryRunningProcessId(LauncherPaths paths)
        {
            using (ServiceHandle manager = OpenManager(SC_MANAGER_CONNECT))
            using (ServiceHandle service = OpenServiceHandle(manager, ServiceName(paths.RootDirectory), SERVICE_QUERY_STATUS))
            {
                if (service.IsInvalid)
                {
                    throw new InvalidOperationException(RepairMessage, new Win32Exception(Marshal.GetLastWin32Error()));
                }
                SERVICE_STATUS_PROCESS status = QueryStatus(service);
                return status.CurrentState == SERVICE_RUNNING ? status.ProcessId : 0;
            }
        }

        private static void RequireRegisteredConfiguration(ServiceHandle service, LauncherPaths paths)
        {
            uint required;
            QueryServiceConfig(service, IntPtr.Zero, 0, out required);
            int error = Marshal.GetLastWin32Error();
            if (error != ERROR_INSUFFICIENT_BUFFER)
            {
                throw new Win32Exception(error, "Windows could not read the SoAI service configuration.");
            }
            IntPtr buffer = Marshal.AllocHGlobal((int)required);
            try
            {
                if (!QueryServiceConfig(service, buffer, required, out required))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not read the SoAI service configuration.");
                }
                QUERY_SERVICE_CONFIG configuration = (QUERY_SERVICE_CONFIG)Marshal.PtrToStructure(buffer, typeof(QUERY_SERVICE_CONFIG));
                if (configuration.ServiceType != SERVICE_WIN32_OWN_PROCESS
                    || configuration.StartType != SERVICE_DEMAND_START
                    || !string.Equals(Marshal.PtrToStringUni(configuration.BinaryPathName), ImagePath(paths), StringComparison.OrdinalIgnoreCase)
                    || !string.Equals(Marshal.PtrToStringUni(configuration.ServiceStartName), LocalSystemAccount, StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException(RepairMessage);
                }
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }

        private static bool StopAndWait(ServiceHandle service, TimeSpan timeout)
        {
            Stopwatch elapsed = Stopwatch.StartNew();
            bool stopRequested = false;
            while (true)
            {
                SERVICE_STATUS_PROCESS status = QueryStatus(service);
                if (status.CurrentState == SERVICE_STOPPED)
                {
                    return true;
                }
                if (!stopRequested && status.CurrentState != SERVICE_STOP_PENDING)
                {
                    SERVICE_STATUS ignored;
                    if (ControlService(service, SERVICE_CONTROL_STOP, out ignored))
                    {
                        stopRequested = true;
                    }
                    else
                    {
                        int error = Marshal.GetLastWin32Error();
                        if (error != ERROR_SERVICE_CANNOT_ACCEPT_CTRL && error != ERROR_SERVICE_NOT_ACTIVE)
                        {
                            throw new Win32Exception(error, "Windows could not stop the SoAI service.");
                        }
                    }
                }
                if (elapsed.Elapsed >= timeout)
                {
                    return false;
                }
                Thread.Sleep(250);
            }
        }

        private static ServiceHandle OpenManager(uint access)
        {
            ServiceHandle manager = OpenSCManager(null, null, access);
            if (manager.IsInvalid)
            {
                int error = Marshal.GetLastWin32Error();
                manager.Dispose();
                throw new Win32Exception(error, "Windows could not open the service manager.");
            }
            return manager;
        }

        private static SERVICE_STATUS_PROCESS QueryStatus(ServiceHandle service)
        {
            SERVICE_STATUS_PROCESS status;
            int returned;
            if (!QueryServiceStatusEx(service, SC_STATUS_PROCESS_INFO, out status, Marshal.SizeOf(typeof(SERVICE_STATUS_PROCESS)), out returned))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not read the SoAI service state.");
            }
            return status;
        }

        private sealed class ServiceHandle : SafeHandleZeroOrMinusOneIsInvalid
        {
            private ServiceHandle()
                : base(true)
            {
            }

            protected override bool ReleaseHandle()
            {
                return CloseServiceHandle(handle);
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SERVICE_STATUS
        {
            public uint ServiceType;
            public uint CurrentState;
            public uint ControlsAccepted;
            public uint Win32ExitCode;
            public uint ServiceSpecificExitCode;
            public uint CheckPoint;
            public uint WaitHint;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SERVICE_STATUS_PROCESS
        {
            public uint ServiceType;
            public uint CurrentState;
            public uint ControlsAccepted;
            public uint Win32ExitCode;
            public uint ServiceSpecificExitCode;
            public uint CheckPoint;
            public uint WaitHint;
            public int ProcessId;
            public uint ServiceFlags;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct QUERY_SERVICE_CONFIG
        {
            public uint ServiceType;
            public uint StartType;
            public uint ErrorControl;
            public IntPtr BinaryPathName;
            public IntPtr LoadOrderGroup;
            public uint TagId;
            public IntPtr Dependencies;
            public IntPtr ServiceStartName;
            public IntPtr DisplayName;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct SERVICE_DESCRIPTION
        {
            public string Description;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SC_ACTION
        {
            public int Type;
            public uint Delay;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct SERVICE_FAILURE_ACTIONS
        {
            public uint ResetPeriod;
            public string RebootMessage;
            public string Command;
            public uint ActionCount;
            public IntPtr Actions;
        }

        [DllImport("advapi32.dll", EntryPoint = "OpenSCManagerW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern ServiceHandle OpenSCManager(string machineName, string databaseName, uint desiredAccess);

        [DllImport("advapi32.dll", EntryPoint = "OpenServiceW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern ServiceHandle OpenServiceHandle(ServiceHandle manager, string serviceName, uint desiredAccess);

        [DllImport("advapi32.dll", EntryPoint = "CreateServiceW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern ServiceHandle CreateServiceHandle(ServiceHandle manager, string serviceName, string displayName, uint desiredAccess, uint serviceType, uint startType, uint errorControl, string binaryPathName, string loadOrderGroup, IntPtr tagId, string dependencies, string serviceStartName, string password);

        [DllImport("advapi32.dll", EntryPoint = "ChangeServiceConfigW", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool ChangeServiceConfig(ServiceHandle service, uint serviceType, uint startType, uint errorControl, string binaryPathName, string loadOrderGroup, IntPtr tagId, string dependencies, string serviceStartName, string password, string displayName);

        [DllImport("advapi32.dll", EntryPoint = "ChangeServiceConfig2W", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool ChangeServiceDescription(ServiceHandle service, uint infoLevel, ref SERVICE_DESCRIPTION information);

        [DllImport("advapi32.dll", EntryPoint = "ChangeServiceConfig2W", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool ChangeServiceFailureActions(ServiceHandle service, uint infoLevel, ref SERVICE_FAILURE_ACTIONS information);

        [DllImport("advapi32.dll", EntryPoint = "QueryServiceConfigW", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool QueryServiceConfig(ServiceHandle service, IntPtr configuration, uint bufferSize, out uint bytesNeeded);

        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool QueryServiceStatusEx(ServiceHandle service, int infoLevel, out SERVICE_STATUS_PROCESS status, int bufferSize, out int bytesNeeded);

        [DllImport("advapi32.dll", EntryPoint = "StartServiceW", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool StartService(ServiceHandle service, uint argumentCount, IntPtr arguments);

        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool ControlService(ServiceHandle service, uint control, out SERVICE_STATUS status);

        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool DeleteService(ServiceHandle service);

        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetServiceObjectSecurity(ServiceHandle service, uint securityInformation, IntPtr securityDescriptor);

        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseServiceHandle(IntPtr handle);
    }

    public static class InstallationSecurity
    {
        public const string RootSecurity = "O:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;BU)";
        public const string DataSecurity = "O:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)";
        private const uint OWNER_SECURITY_INFORMATION = 0x00000001;
        private const uint DACL_SECURITY_INFORMATION = 0x00000004;
        private const uint UNPROTECTED_DACL_SECURITY_INFORMATION = 0x20000000;
        private const uint SECURING_ACCESS = 0x00020000 | 0x00040000 | 0x00080000;
        private const uint SHARE_ALL = 0x00000007;
        private const uint OPEN_EXISTING = 3;
        private const uint OPEN_ENTRY_ITSELF = 0x02000000 | 0x00200000;
        private const uint FILE_ATTRIBUTE_DIRECTORY = 0x00000010;
        private const uint FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400;
        private const uint TOKEN_ADJUST_PRIVILEGES = 0x0020;
        private const uint TOKEN_QUERY = 0x0008;
        private const uint SE_PRIVILEGE_ENABLED = 0x00000002;
        private const int ERROR_NOT_ALL_ASSIGNED = 1300;
        private const int ERROR_FILE_NOT_FOUND = 2;
        private const int ERROR_PATH_NOT_FOUND = 3;
        private const int ERROR_NO_MORE_FILES = 18;
        private static readonly string[] SecuringPrivileges = { "SeBackupPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege" };

        public static string RecordPath(string rootDirectory)
        {
            return Path.Combine(rootDirectory, "data", "state", "windows-file-access-v1.txt");
        }

        public static void Protect(string path, string securityDescriptor)
        {
            using (NativeSecurityDescriptor descriptor = new NativeSecurityDescriptor(securityDescriptor))
            {
                uint information = DACL_SECURITY_INFORMATION;
                if (securityDescriptor.StartsWith("O:", StringComparison.Ordinal))
                {
                    information |= OWNER_SECURITY_INFORMATION;
                }
                if (!SetFileSecurity(LauncherPaths.ToNativeFilesystemPath(path), information, descriptor.Handle))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not apply the SoAI permissions to " + path + ".");
                }
            }
        }

        public static void ResetTree(string installationRoot, string path, string parentSecurity)
        {
            EnableSecuringPrivileges();
            using (NativeSecurityDescriptor container = new NativeSecurityDescriptor(InheritedSecurity(parentSecurity, ";OICIID;")))
            using (NativeSecurityDescriptor leaf = new NativeSecurityDescriptor(InheritedSecurity(parentSecurity, ";ID;")))
            {
                string boundary;
                using (SafeFileHandle root = OpenEntry(LauncherPaths.ToNativeFilesystemPath(installationRoot), false))
                {
                    boundary = FinalPath(root, installationRoot).TrimEnd('\\') + "\\";
                }
                Stack<string> pending = new Stack<string>();
                string initialPath = LauncherPaths.ToNativeFilesystemPath(path);
                pending.Push(initialPath);
                while (pending.Count > 0)
                {
                    string current = pending.Pop();
                    bool entryWasEnumerated = !string.Equals(current, initialPath, StringComparison.OrdinalIgnoreCase);
                    using (SafeFileHandle entry = OpenEntry(current, entryWasEnumerated))
                    {
                        if (entry.IsInvalid) { continue; }
                        NativeFilesystemHandles.FileHandleInformation information;
                        if (!NativeFilesystemHandles.GetFileInformationByHandle(entry, out information))
                        {
                            throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not inspect " + current + " to secure it.");
                        }
                        if (!FinalPath(entry, current).StartsWith(boundary, StringComparison.OrdinalIgnoreCase))
                        {
                            throw new InvalidOperationException(current + " leads outside the SoAI installation, so SoAI did not change its permissions.");
                        }
                        bool directory = (information.Attributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
                        if (!SetKernelObjectSecurity(entry, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION | UNPROTECTED_DACL_SECURITY_INFORMATION, directory ? container.Handle : leaf.Handle))
                        {
                            throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not apply the SoAI permissions to " + current + ".");
                        }
                        if (directory && (information.Attributes & FILE_ATTRIBUTE_REPARSE_POINT) == 0)
                        {
                            foreach (string name in ListDirectory(current))
                            {
                                pending.Push(current + "\\" + name);
                            }
                        }
                    }
                }
            }
        }

        private static string InheritedSecurity(string parentSecurity, string inheritedFlags)
        {
            if (parentSecurity.IndexOf("D:P(", StringComparison.Ordinal) < 0)
            {
                throw new ArgumentException("SoAI permissions must protect the folder that children inherit from.");
            }
            return parentSecurity.Replace("D:P(", "D:AI(").Replace(";OICI;", inheritedFlags);
        }

        private static SafeFileHandle OpenEntry(string nativePath, bool entryWasEnumerated)
        {
            SafeFileHandle handle = NativeFilesystemHandles.CreateFile(nativePath, SECURING_ACCESS, SHARE_ALL, IntPtr.Zero, OPEN_EXISTING, OPEN_ENTRY_ITSELF, IntPtr.Zero);
            if (handle.IsInvalid)
            {
                int error = Marshal.GetLastWin32Error();
                if (entryWasEnumerated && (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND))
                {
                    return handle;
                }
                handle.Dispose();
                throw new Win32Exception(error, "Windows could not open " + nativePath + " to secure it.");
            }
            return handle;
        }

        private static string FinalPath(SafeFileHandle handle, string path)
        {
            StringBuilder buffer = new StringBuilder(1024);
            uint length = GetFinalPathNameByHandle(handle, buffer, (uint)buffer.Capacity, 0);
            if (length >= buffer.Capacity)
            {
                buffer = new StringBuilder((int)length + 1);
                length = GetFinalPathNameByHandle(handle, buffer, (uint)buffer.Capacity, 0);
            }
            if (length == 0 || length >= buffer.Capacity)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not resolve where " + path + " is stored.");
            }
            return buffer.ToString();
        }

        private static List<string> ListDirectory(string nativeDirectory)
        {
            List<string> names = new List<string>();
            SECURING_FIND_DATA data;
            IntPtr search = FindFirstFileEx(nativeDirectory + "\\*", 1, out data, 0, IntPtr.Zero, 2);
            if (search == new IntPtr(-1))
            {
                int error = Marshal.GetLastWin32Error();
                if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND)
                {
                    return names;
                }
                throw new Win32Exception(error, "Windows could not list " + nativeDirectory + " to secure it.");
            }
            try
            {
                do
                {
                    if (data.FileName != "." && data.FileName != "..")
                    {
                        names.Add(data.FileName);
                    }
                }
                while (FindNextFile(search, out data));
                int error = Marshal.GetLastWin32Error();
                if (error != ERROR_NO_MORE_FILES)
                {
                    throw new Win32Exception(error, "Windows could not list " + nativeDirectory + " to secure it.");
                }
            }
            finally
            {
                FindClose(search);
            }
            return names;
        }

        private static void EnableSecuringPrivileges()
        {
            IntPtr token;
            using (Process current = Process.GetCurrentProcess())
            {
                if (!OpenProcessToken(current.Handle, TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, out token))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not prepare SoAI to secure its files.");
                }
            }
            try
            {
                foreach (string privilege in SecuringPrivileges)
                {
                    SECURING_PRIVILEGE state = new SECURING_PRIVILEGE();
                    state.Count = 1;
                    state.Attributes = SE_PRIVILEGE_ENABLED;
                    if (!LookupPrivilegeValue(null, privilege, out state.Luid)
                        || !AdjustTokenPrivileges(token, false, ref state, 0, IntPtr.Zero, IntPtr.Zero))
                    {
                        throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not prepare SoAI to secure its files.");
                    }
                    if (Marshal.GetLastWin32Error() == ERROR_NOT_ALL_ASSIGNED)
                    {
                        throw new InvalidOperationException("Securing SoAI files requires administrator access.");
                    }
                }
            }
            finally
            {
                CloseHandle(token);
            }
        }

        [StructLayout(LayoutKind.Sequential, Pack = 4)]
        private struct SECURING_PRIVILEGE
        {
            public uint Count;
            public long Luid;
            public uint Attributes;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct SECURING_FIND_DATA
        {
            public uint Attributes;
            public System.Runtime.InteropServices.ComTypes.FILETIME Created;
            public System.Runtime.InteropServices.ComTypes.FILETIME Accessed;
            public System.Runtime.InteropServices.ComTypes.FILETIME Modified;
            public uint SizeHigh;
            public uint SizeLow;
            public uint Reserved0;
            public uint Reserved1;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
            public string FileName;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 14)]
            public string AlternateFileName;
        }

        [DllImport("kernel32.dll", EntryPoint = "FindFirstFileExW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr FindFirstFileEx(string fileName, int informationLevel, out SECURING_FIND_DATA data, int searchOperation, IntPtr searchFilter, uint additionalFlags);

        [DllImport("kernel32.dll", EntryPoint = "FindNextFileW", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool FindNextFile(IntPtr search, out SECURING_FIND_DATA data);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool FindClose(IntPtr search);

        [DllImport("kernel32.dll", EntryPoint = "GetFinalPathNameByHandleW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetFinalPathNameByHandle(SafeFileHandle file, StringBuilder path, uint length, uint flags);

        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetKernelObjectSecurity(SafeFileHandle handle, uint securityInformation, IntPtr securityDescriptor);

        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);

        [DllImport("advapi32.dll", EntryPoint = "LookupPrivilegeValueW", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool LookupPrivilegeValue(string system, string name, out long luid);

        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool AdjustTokenPrivileges(IntPtr token, bool disableAll, ref SECURING_PRIVILEGE state, uint length, IntPtr previous, IntPtr returnLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr handle);

        public static bool IsSecured(string rootDirectory)
        {
            string record = RecordPath(rootDirectory);
            if (!File.Exists(record) || (File.GetAttributes(record) & FileAttributes.ReparsePoint) != 0)
            {
                return false;
            }
            SecurityIdentifier owner = (SecurityIdentifier)File.GetAccessControl(record, AccessControlSections.Owner).GetOwner(typeof(SecurityIdentifier));
            return owner.IsWellKnown(WellKnownSidType.LocalSystemSid) || owner.IsWellKnown(WellKnownSidType.BuiltinAdministratorsSid);
        }

        public static void CompleteSecuring(string rootDirectory)
        {
            string record = RecordPath(rootDirectory);
            Directory.CreateDirectory(Path.GetDirectoryName(record));
            if (File.Exists(record))
            {
                File.Delete(record);
            }
            File.WriteAllText(record, "secured\n", new UTF8Encoding(false));
            if (!IsSecured(rootDirectory))
            {
                throw new InvalidOperationException("The SoAI file access record could not be verified at " + record + ".");
            }
        }

        [DllImport("advapi32.dll", EntryPoint = "SetFileSecurityW", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetFileSecurity(string fileName, uint securityInformation, IntPtr securityDescriptor);
    }

    internal sealed class NativeSecurityDescriptor : IDisposable
    {
        public NativeSecurityDescriptor(string descriptor)
        {
            IntPtr handle;
            uint length;
            if (!ConvertStringSecurityDescriptorToSecurityDescriptor(descriptor, 1, out handle, out length))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not prepare a SoAI security descriptor.");
            }
            Handle = handle;
        }

        public IntPtr Handle { get; private set; }

        public void Dispose()
        {
            if (Handle != IntPtr.Zero)
            {
                LocalFree(Handle);
                Handle = IntPtr.Zero;
            }
        }

        [DllImport("advapi32.dll", EntryPoint = "ConvertStringSecurityDescriptorToSecurityDescriptorW", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool ConvertStringSecurityDescriptorToSecurityDescriptor(string descriptor, uint revision, out IntPtr securityDescriptor, out uint securityDescriptorLength);

        [DllImport("kernel32.dll")]
        private static extern IntPtr LocalFree(IntPtr memory);
    }

    public static class NativeFilesystemHandles
    {
        public static Mutex OpenInstallerBootstrapGate(string installationRoot)
        {
            installationRoot = Path.GetFullPath(installationRoot);
            string lockPath = Environment.GetEnvironmentVariable("SOAI_INSTALL_LOCK_HELD_PATH");
            if (!string.IsNullOrEmpty(lockPath))
            {
                string expectedPath = Path.Combine(installationRoot, "data", "state", "locks", "soai.install.lock.d");
                string token = Environment.GetEnvironmentVariable("SOAI_INSTALL_LOCK_HELD_TOKEN");
                long expectedStart;
                int ownerPid;
                if (!string.Equals(Path.GetFullPath(lockPath), expectedPath, StringComparison.OrdinalIgnoreCase)
                    || token == null || token.Length != 64
                    || !long.TryParse(Environment.GetEnvironmentVariable("SOAI_INSTALL_LOCK_OWNER_START_MS"), out expectedStart)
                    || !int.TryParse(File.ReadAllText(LauncherPaths.ToNativeFilesystemPath(Path.Combine(lockPath, "pid"))).Trim(), out ownerPid))
                {
                    throw new InvalidOperationException("Installer handoff ownership is invalid.");
                }
                string storedToken = File.ReadAllText(LauncherPaths.ToNativeFilesystemPath(Path.Combine(lockPath, "token"))).Trim();
                int difference = storedToken.Length ^ token.Length;
                for (int index = 0; index < token.Length; index++)
                {
                    if (index < storedToken.Length) { difference |= token[index] ^ storedToken[index]; }
                    if ((token[index] < '0' || token[index] > '9') && (token[index] < 'a' || token[index] > 'f')) { difference |= 1; }
                }
                using (Process current = Process.GetCurrentProcess())
                using (Process owner = Process.GetProcessById(ownerPid))
                {
                    double ownerSeconds = owner.StartTime.ToUniversalTime().ToFileTimeUtc() / 10000000.0 - 11644473600.0;
                    long ownerStart = (long)Math.Floor(ownerSeconds * 1000.0);
                    if (difference != 0 || NativeFilesystemHandles.GetParentProcessId(current) != ownerPid || owner.HasExited || ownerStart != expectedStart || owner.StartTime.ToUniversalTime() > current.StartTime.ToUniversalTime())
                    {
                        throw new InvalidOperationException("Installer handoff does not identify the live parent process.");
                    }
                }
                return Mutex.OpenExisting("Global\\SoAI.WindowsInstaller.V1");
            }
            bool created;
            Mutex gate = new Mutex(false, "Global\\SoAI.WindowsInstaller.V1", out created);
            if (!created)
            {
                gate.Dispose();
                throw new InvalidOperationException("Another SoAI installer or repair operation is active.");
            }
            return gate;
        }

        public static int GetParentProcessId(Process process)
        {
            INSTALL_PROCESS_IDENTITY identity;
            int returnedLength;
            int status = QueryInstallProcessIdentity(process.Handle, 0, out identity, Marshal.SizeOf(typeof(INSTALL_PROCESS_IDENTITY)), out returnedLength);
            if (status != 0 || identity.Process.ToInt64() != process.Id || process.HasExited)
            {
                throw new InvalidOperationException("The retained installation process identity cannot be verified.");
            }
            return checked((int)identity.ParentProcess.ToInt64());
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct INSTALL_PROCESS_IDENTITY
        {
            public IntPtr ExitStatus;
            public IntPtr Peb;
            public IntPtr Affinity;
            public IntPtr Priority;
            public IntPtr Process;
            public IntPtr ParentProcess;
        }

        [DllImport("ntdll.dll", EntryPoint = "NtQueryInformationProcess")]
        private static extern int QueryInstallProcessIdentity(IntPtr process, int informationClass, out INSTALL_PROCESS_IDENTITY information, int length, out int returnedLength);


        public static List<SafeFileHandle> RetainDirectoryAncestors(string path)
        {
            List<string> paths = new List<string>();
            string current = Path.GetFullPath(path);
            while (current != null)
            {
                paths.Add(current);
                if (string.Equals(current, Path.GetPathRoot(current), StringComparison.OrdinalIgnoreCase)) { break; }
                string parent = Path.GetDirectoryName(current.TrimEnd('\\'));
                if (string.Equals(parent, current, StringComparison.OrdinalIgnoreCase)) { break; }
                current = parent;
            }
            paths.Reverse();
            List<SafeFileHandle> handles = new List<SafeFileHandle>();
            try
            {
                foreach (string ancestor in paths)
                {
                    string nativeAncestor = LauncherPaths.ToNativeFilesystemPath(ancestor);
                    SafeFileHandle handle = CreateFile(nativeAncestor, 0x80, 3, IntPtr.Zero, 3, 0x02200000, IntPtr.Zero);
                    handles.Add(handle);
                    FileHandleInformation information;
                    if (handle.IsInvalid || !GetFileInformationByHandle(handle, out information) || (information.Attributes & 0x410) != 0x10
                        || (GetFileAttributes(nativeAncestor) & 0x400) != 0)
                    {
                        throw new InvalidOperationException("An uninstall ancestor cannot be verified as a retained directory.");
                    }
                }
                return handles;
            }
            catch
            {
                foreach (SafeFileHandle handle in handles) { handle.Dispose(); }
                throw;
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SecurityAttributes
        {
            public int Length;
            public IntPtr Descriptor;
            public bool Inherit;
        }

        [DllImport("kernel32.dll", EntryPoint = "CreateDirectoryW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateSecuredDirectory(string path, ref SecurityAttributes attributes);

        [DllImport("kernel32.dll", EntryPoint = "CreateMutexW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateOwnershipMutex(ref SecurityAttributes attributes, bool initialOwner, string name);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);

        public static void WriteNewDurableFile(string path, string text)
        {
            byte[] bytes = new UTF8Encoding(false).GetBytes(text);
            using (FileStream stream = new FileStream(LauncherPaths.ToNativeFilesystemPath(path), FileMode.CreateNew, FileAccess.Write, FileShare.Read))
            {
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }
        }

        public static void CreateProtectedDirectory(string path, string security)
        {
            using (NativeSecurityDescriptor descriptor = new NativeSecurityDescriptor(security))
            {
                SecurityAttributes attributes = new SecurityAttributes();
                attributes.Length = Marshal.SizeOf(typeof(SecurityAttributes));
                attributes.Descriptor = descriptor.Handle;
                if (!CreateSecuredDirectory(LauncherPaths.ToNativeFilesystemPath(path), ref attributes))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Protected uninstall staging could not be created exclusively.");
                }
            }
        }

        public static Mutex AcquireSharedResourceGate()
        {
            const string name = "Global\\SoAI.SharedResourceOwnership.V1";
            using (NativeSecurityDescriptor descriptor = new NativeSecurityDescriptor("D:P(A;;GA;;;SY)(A;;GA;;;BA)"))
            {
                SecurityAttributes attributes = new SecurityAttributes();
                attributes.Length = Marshal.SizeOf(typeof(SecurityAttributes));
                attributes.Descriptor = descriptor.Handle;
                IntPtr native = CreateOwnershipMutex(ref attributes, false, name);
                if (native == IntPtr.Zero) { throw new Win32Exception(Marshal.GetLastWin32Error(), "Shared backend ownership coordination is unavailable."); }
                try
                {
                    Mutex gate = Mutex.OpenExisting(name);
                    try
                    {
                        try
                        {
                            if (!gate.WaitOne(TimeSpan.FromSeconds(150)))
                            {
                                throw new TimeoutException("Shared backend ownership is busy. Retry after the current installation operation completes.");
                            }
                        }
                        catch (AbandonedMutexException) { }
                        return gate;
                    }
                    catch { gate.Dispose(); throw; }
                }
                finally { CloseHandle(native); }
            }
        }

        public static void RemoveEmptySharedOwnership(string root, SafeFileHandle ownership)
        {
            string nativeRoot = LauncherPaths.ToNativeFilesystemPath(root);
            FileHandleInformation information;
            if (ownership.IsInvalid || !GetFileInformationByHandle(ownership, out information) || (information.Attributes & 0x410) != 0 || information.Links != 1)
            {
                throw new InvalidOperationException("Shared ownership coordination is not a verified regular file.");
            }
            foreach (string entry in Directory.GetFileSystemEntries(nativeRoot))
            {
                string name = Path.GetFileName(entry);
                if (name != "shared-resource-claims-v1.json" && name != "shared-resource-ownership-v1.lock")
                {
                    throw new InvalidOperationException("Shared ownership acquired an unrelated entry during final cleanup.");
                }
            }
            File.Delete(Path.Combine(nativeRoot, "shared-resource-claims-v1.json"));
            SetDeleteDisposition(ownership, "Empty shared ownership coordination could not be removed.");
        }

        public static void SetDeleteDisposition(SafeFileHandle handle, string failureMessage)
        {
            IntPtr disposition = Marshal.AllocHGlobal(1);
            try
            {
                Marshal.WriteByte(disposition, 1);
                if (!SetFileInformationByHandle(handle, 4, disposition, 1))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), failureMessage);
                }
            }
            finally { Marshal.FreeHGlobal(disposition); }
        }

        public static void ClearReadOnlyAttribute(SafeFileHandle handle, uint attributes, string failureMessage)
        {
            uint updated = attributes & ~0x1u;
            IntPtr information = Marshal.AllocHGlobal(40);
            try
            {
                for (int offset = 0; offset < 40; offset += 8) { Marshal.WriteInt64(information, offset, 0); }
                Marshal.WriteInt32(information, 32, unchecked((int)(updated == 0 ? 0x80u : updated)));
                if (!SetFileInformationByHandle(handle, 0, information, 40))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), failureMessage);
                }
            }
            finally { Marshal.FreeHGlobal(information); }
        }

        public static void ScheduleRemovalAtRestart(string path)
        {
            if (!MoveFileEx(LauncherPaths.ToNativeFilesystemPath(path), null, 0x4))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows did not accept removal at the next restart.");
            }
        }

        [DllImport("kernel32.dll", EntryPoint = "MoveFileExW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool MoveFileEx(string existingFileName, string newFileName, uint flags);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern SafeFileHandle CreateFile(string fileName, uint desiredAccess, uint shareMode, IntPtr securityAttributes, uint creationDisposition, uint flagsAndAttributes, IntPtr templateFile);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern bool CreateDirectory(string path, IntPtr securityAttributes);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern uint GetFileAttributes(string path);

        [StructLayout(LayoutKind.Sequential)]
        internal struct FileHandleInformation
        {
            public uint Attributes;
            public System.Runtime.InteropServices.ComTypes.FILETIME Created;
            public System.Runtime.InteropServices.ComTypes.FILETIME Accessed;
            public System.Runtime.InteropServices.ComTypes.FILETIME Modified;
            public uint VolumeSerial;
            public uint SizeHigh;
            public uint SizeLow;
            public uint Links;
            public uint IndexHigh;
            public uint IndexLow;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct LockRenameInformation
        {
            public byte ReplaceExisting;
            public IntPtr RootDirectory;
            public uint NameLength;
            public char Name;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool GetFileInformationByHandle(SafeFileHandle handle, out FileHandleInformation information);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetFileInformationByHandle(SafeFileHandle handle, int informationClass, IntPtr information, uint size);

        public static string RecoverAbandonedInstallLock(string lockDirectory)
        {
            string nativeDirectory = LauncherPaths.ToNativeFilesystemPath(Path.GetFullPath(lockDirectory));
            if (!Directory.Exists(nativeDirectory) && GetFileAttributes(nativeDirectory) == uint.MaxValue)
            {
                int failure = Marshal.GetLastWin32Error();
                if (failure == 2 || failure == 3) { return null; }
                throw new Win32Exception(failure, "The installation lock cannot be inspected.");
            }
            using (Mutex gate = Mutex.OpenExisting("Global\\SoAI.WindowsInstaller.V1"))
            using (SafeFileHandle directory = CreateFile(nativeDirectory, 0x10080, 3, IntPtr.Zero, 3, 0x02200000, IntPtr.Zero))
            {
                FileHandleInformation identity;
                if (directory.IsInvalid || !GetFileInformationByHandle(directory, out identity))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "The installation lock cannot be retained safely.");
                }
                if ((identity.Attributes & 0x410) != 0x10)
                {
                    throw new InvalidOperationException("The installation lock is not a regular retained directory.");
                }
                List<FileStream> evidence = new List<FileStream>();
                try
                {
                    foreach (string entry in Directory.GetFileSystemEntries(nativeDirectory))
                    {
                        string name = Path.GetFileName(entry);
                        if (name != "pid" && name != "token" && name != "owner-start-ms")
                        {
                            throw new InvalidOperationException("Unrecognized installation lock evidence requires repair and has been retained.");
                        }
                    }
                    string pidText = ReadLockEvidence(Path.Combine(nativeDirectory, "pid"), evidence);
                    string token = ReadLockEvidence(Path.Combine(nativeDirectory, "token"), evidence);
                    int ownerPid;
                    if (!int.TryParse(pidText, NumberStyles.None, CultureInfo.InvariantCulture, out ownerPid) || ownerPid <= 0
                        || !Regex.IsMatch(token, "\\A[0-9a-f]{64}\\z", RegexOptions.CultureInvariant))
                    {
                        throw new InvalidOperationException("Installation lock ownership is malformed and has been retained for repair.");
                    }
                    string startPath = Path.Combine(nativeDirectory, "owner-start-ms");
                    long? expectedStart = null;
                    uint startAttributes = GetFileAttributes(startPath);
                    if (startAttributes != uint.MaxValue)
                    {
                        long parsedStart;
                        if (!long.TryParse(ReadLockEvidence(startPath, evidence), NumberStyles.None, CultureInfo.InvariantCulture, out parsedStart) || parsedStart <= 0)
                        {
                            throw new InvalidOperationException("Installation lock process identity is malformed and has been retained.");
                        }
                        expectedStart = parsedStart;
                    }
                    else
                    {
                        int failure = Marshal.GetLastWin32Error();
                        if (failure != 2 && failure != 3) { throw new Win32Exception(failure, "Installation lock process identity cannot be inspected."); }
                    }
                    Process owner = null;
                    try { owner = Process.GetProcessById(ownerPid); }
                    catch (ArgumentException) { owner = null; }
                    if (owner != null)
                    {
                        using (owner)
                        {
                            if (!owner.HasExited)
                            {
                                double created = owner.StartTime.ToUniversalTime().ToFileTimeUtc() / 10000000.0 - 11644473600.0;
                                long started = (long)Math.Floor(created * 1000.0);
                                if (!expectedStart.HasValue || expectedStart.Value == started) { return null; }
                            }
                        }
                    }
                }
                finally
                {
                    foreach (FileStream stream in evidence) { stream.Dispose(); }
                }
                string retainedPath = Path.GetFullPath(lockDirectory) + ".abandoned-" + Guid.NewGuid().ToString("N");
                RenameRetainedLock(directory, LauncherPaths.ToNativeFilesystemPath(retainedPath));
                return retainedPath;
            }
        }

        private static string ReadLockEvidence(string path, List<FileStream> retained)
        {
            SafeFileHandle handle = CreateFile(path, 0x80000000, 1, IntPtr.Zero, 3, 0x00200000, IntPtr.Zero);
            FileHandleInformation information;
            if (handle.IsInvalid || !GetFileInformationByHandle(handle, out information))
            {
                int failure = Marshal.GetLastWin32Error();
                handle.Dispose();
                throw new Win32Exception(failure, "Installation lock ownership evidence cannot be retained.");
            }
            if ((information.Attributes & 0x410) != 0 || information.SizeHigh != 0 || information.SizeLow > 128)
            {
                handle.Dispose();
                throw new InvalidOperationException("Installation lock ownership evidence is not a bounded regular file.");
            }
            FileStream stream = new FileStream(handle, FileAccess.Read);
            retained.Add(stream);
            using (StreamReader reader = new StreamReader(stream, new UTF8Encoding(false, true), false, 128, true))
            {
                return reader.ReadToEnd().Trim();
            }
        }

        private static void RenameRetainedLock(SafeFileHandle handle, string destination)
        {
            byte[] name = Encoding.Unicode.GetBytes(destination);
            int nameOffset = Marshal.OffsetOf(typeof(LockRenameInformation), "Name").ToInt32();
            int size = checked(nameOffset + name.Length + sizeof(char));
            IntPtr information = Marshal.AllocHGlobal(size);
            try
            {
                Marshal.WriteInt32(information, 0);
                Marshal.WriteIntPtr(information, Marshal.OffsetOf(typeof(LockRenameInformation), "RootDirectory").ToInt32(), IntPtr.Zero);
                Marshal.WriteInt32(information, Marshal.OffsetOf(typeof(LockRenameInformation), "NameLength").ToInt32(), name.Length);
                Marshal.Copy(name, 0, IntPtr.Add(information, nameOffset), name.Length);
                Marshal.WriteInt16(information, nameOffset + name.Length, 0);
                if (!SetFileInformationByHandle(handle, 3, information, (uint)size))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Abandoned installation lock evidence could not be retained for recovery.");
                }
            }
            finally { Marshal.FreeHGlobal(information); }
        }
    }

    public sealed class NativeImageAllowance
    {
        internal NativeImageAllowance(double seconds, double ordinarySeconds, int imageCount, bool inventoryComplete)
        {
            Seconds = seconds;
            OrdinarySeconds = ordinarySeconds;
            ImageCount = imageCount;
            InventoryComplete = inventoryComplete;
        }

        public double Seconds { get; private set; }
        public double OrdinarySeconds { get; private set; }
        public int ImageCount { get; private set; }
        public bool InventoryComplete { get; private set; }
        public int WholeSeconds { get { return (int)Math.Ceiling(Seconds); } }
        public TimeSpan Duration { get { return TimeSpan.FromSeconds(Seconds); } }

        public string DescribeTimeout(string subject)
        {
            string minutes = ((int)Math.Ceiling(Seconds / 60)).ToString(CultureInfo.InvariantCulture);
            return subject + " did not become ready within " + minutes + " minutes." + (ImageCount > 0 ? " Windows security checks of newly installed files can delay the first start." : string.Empty);
        }
    }

    public static class NativeImageBudget
    {
        public const int SecondsPerImage = 60;
        private static readonly string[] ImageExtensions = new string[] { ".dll", ".exe", ".pyd" };

        public static NativeImageAllowance Calculate(double ordinarySeconds, string[] roots, string[] shallowRoots, string[] excludedNames, int pendingImageCount)
        {
            int count = Math.Max(0, pendingImageCount);
            bool complete = true;
            try
            {
                count += CountImages(roots, shallowRoots, excludedNames);
            }
            catch (IOException)
            {
                complete = false;
            }
            catch (UnauthorizedAccessException)
            {
                complete = false;
            }
            return new NativeImageAllowance(ordinarySeconds + (double)SecondsPerImage * count, ordinarySeconds, count, complete);
        }

        public static int CountImages(string[] roots, string[] shallowRoots, string[] excludedNames)
        {
            HashSet<string> images = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            HashSet<string> excluded = new HashSet<string>(excludedNames ?? new string[0], StringComparer.OrdinalIgnoreCase);
            foreach (string root in roots ?? new string[0])
            {
                CollectImages(root, true, excluded, images);
            }
            foreach (string root in shallowRoots ?? new string[0])
            {
                CollectImages(root, false, excluded, images);
            }
            return images.Count;
        }

        private static void CollectImages(string root, bool recursive, HashSet<string> excluded, HashSet<string> images)
        {
            if (string.IsNullOrWhiteSpace(root))
            {
                return;
            }
            string nativeRoot = LauncherPaths.ToNativeFilesystemPath(root);
            if (File.Exists(nativeRoot))
            {
                AddImage(nativeRoot, images);
                return;
            }
            if (!Directory.Exists(nativeRoot) || IsReparsePoint(nativeRoot))
            {
                return;
            }
            Stack<string> pending = new Stack<string>();
            pending.Push(nativeRoot);
            while (pending.Count > 0)
            {
                string directory = pending.Pop();
                foreach (string file in Directory.GetFiles(directory))
                {
                    AddImage(file, images);
                }
                if (!recursive)
                {
                    continue;
                }
                foreach (string child in Directory.GetDirectories(directory))
                {
                    if (!excluded.Contains(Path.GetFileName(child)) && !IsReparsePoint(child))
                    {
                        pending.Push(child);
                    }
                }
            }
        }

        private static void AddImage(string path, HashSet<string> images)
        {
            string extension = Path.GetExtension(path);
            foreach (string imageExtension in ImageExtensions)
            {
                if (string.Equals(extension, imageExtension, StringComparison.OrdinalIgnoreCase) && !IsReparsePoint(path))
                {
                    images.Add(path);
                    return;
                }
            }
        }

        private static bool IsReparsePoint(string path)
        {
            return (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0;
        }
    }

    public sealed class SharingConflictWait : IDisposable
    {
        public const double OrdinarySeconds = 30;
        private const double InitialDelaySeconds = 0.25;
        private const double MaximumDelaySeconds = 2;
        private const double JitterRatio = 0.1;
        private static readonly Random Jitter = new Random();
        private readonly string source;
        private readonly string destination;
        private readonly string identity;
        private readonly SafeFileHandle sourceHandle;
        private readonly double allowanceSeconds;
        private readonly Stopwatch elapsed;
        private int attempt;

        private SharingConflictWait(string source, string destination, double allowanceSeconds)
        {
            this.source = LauncherPaths.ToNativeFilesystemPath(source);
            this.destination = LauncherPaths.ToNativeFilesystemPath(destination);
            this.allowanceSeconds = allowanceSeconds;
            sourceHandle = NativeFilesystemHandles.CreateFile(this.source, 0x80, 7, IntPtr.Zero, 3, 0x02200000, IntPtr.Zero);
            try
            {
                identity = ReadIdentity(sourceHandle);
            }
            catch
            {
                sourceHandle.Dispose();
                throw;
            }
            elapsed = Stopwatch.StartNew();
        }

        public static SharingConflictWait Begin(string source, string destination)
        {
            NativeImageAllowance allowance = NativeImageBudget.Calculate(OrdinarySeconds, new string[] { source }, new string[0], new string[0], 0);
            return new SharingConflictWait(source, destination, allowance.Seconds);
        }

        public static bool IsSharingConflict(Exception exception)
        {
            for (Exception current = exception; current != null; current = current.InnerException)
            {
                IOException failure = current as IOException;
                if (failure != null)
                {
                    int code = failure.HResult & 0xFFFF;
                    return (failure.HResult & unchecked((int)0xFFFF0000)) == unchecked((int)0x80070000) && (code == 32 || code == 33);
                }
            }
            return false;
        }

        public bool ShouldRetry(Exception exception)
        {
            if (sourceHandle.IsClosed) { throw new ObjectDisposedException("SharingConflictWait"); }
            double remaining = allowanceSeconds - elapsed.Elapsed.TotalSeconds;
            if (!IsSharingConflict(exception) || remaining <= 0 || File.Exists(destination) || Directory.Exists(destination))
            {
                return false;
            }
            double delay = Math.Min(MaximumDelaySeconds, InitialDelaySeconds * Math.Pow(2, Math.Min(attempt, 16)));
            lock (Jitter)
            {
                delay += delay * JitterRatio * Jitter.NextDouble();
            }
            Thread.Sleep(TimeSpan.FromSeconds(Math.Min(remaining, delay)));
            attempt++;
            if (!string.Equals(ReadIdentity(source), identity, StringComparison.Ordinal))
            {
                throw new IOException("A managed file changed while SoAI waited for another program to release it.", exception);
            }
            return true;
        }

        private static string ReadIdentity(string path)
        {
            using (SafeFileHandle handle = NativeFilesystemHandles.CreateFile(path, 0x80, 7, IntPtr.Zero, 3, 0x02200000, IntPtr.Zero))
            {
                return ReadIdentity(handle);
            }
        }

        private static string ReadIdentity(SafeFileHandle handle)
        {
            NativeFilesystemHandles.FileHandleInformation information;
            if (handle.IsInvalid || !NativeFilesystemHandles.GetFileInformationByHandle(handle, out information))
            {
                int failure = Marshal.GetLastWin32Error();
                if (failure == 2 || failure == 3) { return string.Empty; }
                throw new Win32Exception(failure, "A managed file identity could not be read.");
            }
            return string.Join(":", new string[]
            {
                information.VolumeSerial.ToString(CultureInfo.InvariantCulture),
                information.IndexHigh.ToString(CultureInfo.InvariantCulture),
                information.IndexLow.ToString(CultureInfo.InvariantCulture),
                (information.Attributes & 0x410).ToString(CultureInfo.InvariantCulture),
            });
        }

        public void Dispose()
        {
            sourceHandle.Dispose();
        }
    }

    public sealed class NativeBackendJob : IDisposable
    {
        public static string ReadProcessImagePath(IntPtr process)
        {
            StringBuilder image = new StringBuilder(32768);
            int length = image.Capacity;
            if (!QueryFullProcessImageName(process, 0, image, ref length))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "The retained Windows process image could not be verified.");
            }
            return LauncherPaths.RemoveWindowsPathNamespace(image.ToString());
        }

        private const uint CREATE_SUSPENDED = 0x00000004;
        private const uint CREATE_NO_WINDOW = 0x08000000;
        private const uint GENERIC_READ = 0x80000000;
        private const uint FILE_SHARE_READ = 0x00000001;
        private const uint FILE_SHARE_WRITE = 0x00000002;
        private const uint OPEN_EXISTING = 3;
        private const uint STARTF_USESHOWWINDOW = 0x00000001;
        private const uint STARTF_USESTDHANDLES = 0x00000100;
        private const uint HANDLE_FLAG_INHERIT = 0x00000001;
        private const uint JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800;
        private const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
        private const int JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9;
        private const int JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1;
        private const uint WAIT_TIMEOUT = 258;
        private const int SYSTEM_EXTENDED_HANDLE_INFORMATION = 64;
        private const uint STATUS_INFO_LENGTH_MISMATCH = 0xC0000004;
        private const uint PROCESS_DUP_HANDLE = 0x00000040;
        private const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x00001000;
        private const uint DUPLICATE_SAME_ACCESS = 0x00000002;
        private readonly Process process;
        private readonly bool allowBreakaway;
        private IntPtr jobHandle;
        private bool committed;

        private NativeBackendJob(Process process, IntPtr jobHandle, bool allowBreakaway)
        {
            this.process = process;
            this.allowBreakaway = allowBreakaway;
            this.jobHandle = jobHandle;
        }

        public bool HasExited { get { return process.HasExited; } }
        public int ExitCode { get { return process.ExitCode; } }
        public Process ProcessHandle { get { return process; } }

        internal static NativeBackendJob StartServiceStop(LauncherPaths paths, TimeSpan remaining)
        {
            double expires = (double)Stopwatch.GetTimestamp() / Stopwatch.Frequency + Math.Max(0, remaining.TotalSeconds);
            string python = ResolveProcessPath(paths.ResolveStopPythonExecutable(), preserveExecutableNamespace: true);
            BackendProcess.RequireBackendMain(paths);
            BackendProcess.ConfigureBackendEnvironment(paths);
            string script = "import logging,os,sys\n"
                + "from app.cli.instance_control import handle_stop\n"
                + "from app.cli.windows_lifecycle_request import verify_stopped_instance\n"
                + "os.environ['SOAI_WINDOWS_STOP_DEADLINE_SECONDS']=sys.argv[2]\n"
                + "logging.basicConfig(level=logging.INFO)\n"
                + "logger=logging.getLogger('launcher.service_stop')\n"
                + "sys.exit(0 if verify_stopped_instance(sys.argv[1],logger,expected_edition='soai-core') else handle_stop(sys.argv[1],logger,expected_edition='soai-core'))";
            return StartProcess(python, "-P -c " + BackendProcess.Quote(script) + " " + BackendProcess.Quote(paths.RootDirectory)
                + " " + BackendProcess.Quote(expires.ToString("R", CultureInfo.InvariantCulture)), paths.RootDirectory,
                Path.Combine(paths.RootDirectory, "data", "logs", "soai-launcher.log"), false);
        }

        internal static NativeBackendJob Start(LauncherPaths paths, string[] args)
        {
            string python = ResolveProcessPath(LauncherCommand.IsStopCommand(args) ? paths.ResolveStopPythonExecutable() : BackendProcess.ResolvePython(paths, args), preserveExecutableNamespace: true);
            BackendProcess.RequireBackendMain(paths);
            BackendProcess.ConfigureBackendEnvironment(paths);
            return StartProcess(
                python,
                BackendProcess.Quote(paths.BackendMain) + BackendProcess.BuildArgumentString(args),
                paths.RootDirectory,
                Path.Combine(paths.RootDirectory, "data", "logs", "soai-launcher.log"));
        }

        [DllImport("kernel32.dll", EntryPoint = "GetStdHandle", SetLastError = true)]
        private static extern IntPtr GetConsoleStandardHandle(int stream);

        public void Commit()
        {
            SetKillOnJobClose(jobHandle, false, allowBreakaway);
            committed = true;
        }

        internal void CancelControl()
        {
            if (jobHandle == IntPtr.Zero) { return; }
            try
            {
                if (!TerminateJobObject(jobHandle, 1))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "The owned stop control could not be cancelled.");
                }
            }
            finally
            {
                CloseHandle(jobHandle);
                jobHandle = IntPtr.Zero;
                process.Dispose();
            }
        }

        public bool HasActiveProcesses()
        {
            return CountActiveProcesses(jobHandle) > 0;
        }

        public static NativeBackendJob StartProcess(string executable, string arguments, string workingDirectory, string logPath)
        {
            return StartProcess(executable, arguments, workingDirectory, logPath, true);
        }

        internal static NativeBackendJob StartProcess(string executable, string arguments, string workingDirectory, string logPath, bool allowBreakaway)
        {
            STARTUPINFO startupInfo = CreateStartupInfo();
            string logDirectory = Path.GetDirectoryName(Path.GetFullPath(logPath));
            Directory.CreateDirectory(logDirectory);
            using (SafeFileHandle input = OpenNullInput())
            using (FileStream output = new FileStream(logPath, FileMode.Append, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete))
            {
                startupInfo.hStdInput = input.DangerousGetHandle();
                startupInfo.hStdOutput = output.SafeFileHandle.DangerousGetHandle();
                startupInfo.hStdError = startupInfo.hStdOutput;
                return StartProcessWithStreams(executable, arguments, workingDirectory, startupInfo, false, allowBreakaway);
            }
        }

        internal static NativeBackendJob StartConsoleProcess(string executable, string arguments, string workingDirectory)
        {
            STARTUPINFO startupInfo = CreateStartupInfo();
            startupInfo.hStdInput = GetConsoleStandardHandle(-10);
            startupInfo.hStdOutput = GetConsoleStandardHandle(-11);
            startupInfo.hStdError = GetConsoleStandardHandle(-12);
            return StartProcessWithStreams(executable, arguments, workingDirectory, startupInfo, true, false);
        }

        public static int ReleaseInheritedKillOnCloseJobs(string rootDirectory)
        {
            IntPtr currentProcess = GetCurrentProcess();
            bool inJob;
            if (!IsProcessInJob(currentProcess, IntPtr.Zero, out inJob))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows job membership could not be inspected.");
            }
            if (!inJob)
            {
                return 0;
            }
            string launcherPath = Path.Combine(Path.GetFullPath(rootDirectory), "soai.exe");
            int currentProcessId;
            using (Process current = Process.GetCurrentProcess())
            {
                currentProcessId = current.Id;
            }
            IntPtr probe = CreateJobObject(IntPtr.Zero, null);
            if (probe == IntPtr.Zero)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows job ownership could not be inspected.");
            }
            int released = 0;
            try
            {
                byte[] table = QuerySystemHandleTable();
                int pointerSize = IntPtr.Size;
                int entrySize = 3 * pointerSize + 16;
                long count = ReadPointerSized(table, 0);
                if (count < 0 || 2L * pointerSize + count * entrySize > table.Length)
                {
                    throw new InvalidOperationException("Windows job ownership could not be inspected.");
                }
                int jobType = -1;
                for (long index = 0; index < count; index++)
                {
                    int offset = checked((int)(2 * pointerSize + index * entrySize));
                    if (ReadPointerSized(table, offset + pointerSize) == currentProcessId && ReadPointerSized(table, offset + 2 * pointerSize) == probe.ToInt64())
                    {
                        jobType = BitConverter.ToUInt16(table, offset + 3 * pointerSize + 6);
                        break;
                    }
                }
                if (jobType < 0)
                {
                    throw new InvalidOperationException("Windows job ownership could not be inspected.");
                }
                Dictionary<long, IntPtr> launcherOwners = new Dictionary<long, IntPtr>();
                try
                {
                    for (long index = 0; index < count; index++)
                    {
                        int offset = checked((int)(2 * pointerSize + index * entrySize));
                        if (BitConverter.ToUInt16(table, offset + 3 * pointerSize + 6) != jobType)
                        {
                            continue;
                        }
                        long ownerId = ReadPointerSized(table, offset + pointerSize);
                        if (ownerId == currentProcessId)
                        {
                            continue;
                        }
                        IntPtr owner;
                        if (!launcherOwners.TryGetValue(ownerId, out owner))
                        {
                            owner = OpenLauncherOwner(ownerId, launcherPath);
                            launcherOwners[ownerId] = owner;
                        }
                        if (owner == IntPtr.Zero)
                        {
                            continue;
                        }
                        IntPtr job;
                        if (!DuplicateHandle(owner, new IntPtr(ReadPointerSized(table, offset + 2 * pointerSize)), currentProcess, out job, 0, false, DUPLICATE_SAME_ACCESS))
                        {
                            continue;
                        }
                        try
                        {
                            bool member;
                            if (!IsProcessInJob(currentProcess, job, out member) || !member)
                            {
                                continue;
                            }
                            JOBOBJECT_EXTENDED_LIMIT_INFORMATION information;
                            int informationLength = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
                            if (!QueryInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, out information, informationLength, IntPtr.Zero))
                            {
                                throw new Win32Exception(Marshal.GetLastWin32Error(), "The previous launcher job could not be inspected.");
                            }
                            if ((information.BasicLimitInformation.LimitFlags & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE) == 0)
                            {
                                continue;
                            }
                            information.BasicLimitInformation.LimitFlags &= ~JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                            if (!SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ref information, informationLength))
                            {
                                throw new Win32Exception(Marshal.GetLastWin32Error(), "The previous launcher job could not release this maintenance.");
                            }
                            released++;
                        }
                        finally
                        {
                            CloseHandle(job);
                        }
                    }
                }
                finally
                {
                    foreach (IntPtr owner in launcherOwners.Values)
                    {
                        if (owner != IntPtr.Zero)
                        {
                            CloseHandle(owner);
                        }
                    }
                }
            }
            finally
            {
                CloseHandle(probe);
            }
            return released;
        }

        private static IntPtr OpenLauncherOwner(long processId, string launcherPath)
        {
            IntPtr owner = OpenProcess(PROCESS_DUP_HANDLE | PROCESS_QUERY_LIMITED_INFORMATION, false, unchecked((uint)processId));
            if (owner == IntPtr.Zero)
            {
                return IntPtr.Zero;
            }
            StringBuilder image = new StringBuilder(32768);
            int imageLength = image.Capacity;
            if (QueryFullProcessImageName(owner, 0, image, ref imageLength))
            {
                string imagePath = image.ToString(0, imageLength);
                if (imagePath.StartsWith(@"\\?\", StringComparison.Ordinal))
                {
                    imagePath = imagePath.Substring(4);
                }
                if (string.Equals(imagePath, launcherPath, StringComparison.OrdinalIgnoreCase))
                {
                    return owner;
                }
            }
            CloseHandle(owner);
            return IntPtr.Zero;
        }

        private static byte[] QuerySystemHandleTable()
        {
            int length = 1 << 20;
            while (true)
            {
                IntPtr buffer = Marshal.AllocHGlobal(length);
                try
                {
                    int required;
                    uint status = NtQuerySystemInformation(SYSTEM_EXTENDED_HANDLE_INFORMATION, buffer, length, out required);
                    if (status == STATUS_INFO_LENGTH_MISMATCH)
                    {
                        if (length >= (1 << 29))
                        {
                            throw new InvalidOperationException("Windows job ownership could not be inspected.");
                        }
                        length = Math.Max(length * 2, required + (1 << 16));
                        continue;
                    }
                    if (status != 0)
                    {
                        throw new InvalidOperationException("Windows job ownership could not be inspected (NTSTATUS 0x" + status.ToString("X8", CultureInfo.InvariantCulture) + ").");
                    }
                    byte[] table = new byte[length];
                    Marshal.Copy(buffer, table, 0, length);
                    return table;
                }
                finally
                {
                    Marshal.FreeHGlobal(buffer);
                }
            }
        }

        private static long ReadPointerSized(byte[] table, int offset)
        {
            return IntPtr.Size == 8 ? BitConverter.ToInt64(table, offset) : BitConverter.ToUInt32(table, offset);
        }

        public static void PrepareTemporaryEnvironment()
        {
            Dictionary<string, string> resolved = new Dictionary<string, string>();
            foreach (string name in new string[] { "TEMP", "TMP", "TMPDIR" })
            {
                string value = Environment.GetEnvironmentVariable(name);
                if (!string.IsNullOrEmpty(value))
                {
                    resolved.Add(name, ResolveEnvironmentValue(name, value));
                }
            }
            foreach (KeyValuePair<string, string> entry in resolved)
            {
                Environment.SetEnvironmentVariable(entry.Key, entry.Value);
            }
        }

        private static string ResolveEnvironmentValue(string name, string value)
        {
            if (!string.IsNullOrEmpty(value)
                && (string.Equals(name, "TEMP", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(name, "TMP", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(name, "TMPDIR", StringComparison.OrdinalIgnoreCase)))
            {
                return ResolveProcessPath(value, true);
            }
            return value;
        }

        public static NativeBackendJob StartLoggedProcess(ProcessStartInfo startInfo, string stdoutLogPath, string stderrLogPath)
        {
            if (startInfo == null || startInfo.UseShellExecute || startInfo.RedirectStandardInput)
            {
                throw new ArgumentException("Logged native commands require direct execution with inherited null input.");
            }
            string executableName = Path.GetFileName(startInfo.FileName);
            bool preservePythonNamespace = Path.IsPathRooted(startInfo.FileName)
                && (string.Equals(executableName, "python.exe", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(executableName, "pythonw.exe", StringComparison.OrdinalIgnoreCase));
            string executable = ResolveProcessPath(startInfo.FileName, preserveExecutableNamespace: preservePythonNamespace);
            string workingDirectory = ResolveProcessPath(startInfo.WorkingDirectory, true);
            List<string> names = new List<string>();
            foreach (string name in startInfo.EnvironmentVariables.Keys) { names.Add(name); }
            names.Sort(StringComparer.OrdinalIgnoreCase);
            StringBuilder environmentText = new StringBuilder();
            foreach (string name in names)
            {
                string value = startInfo.EnvironmentVariables[name];
                if (value == null) { continue; }
                if (name.Length == 0 || name.IndexOf('\0') >= 0 || value.IndexOf('\0') >= 0
                    || (name.IndexOf('=') >= 0 && !(name.Length == 3 && name[0] == '=' && name[2] == ':')))
                {
                    throw new ArgumentException("A native command environment entry is invalid.");
                }
                value = ResolveEnvironmentValue(name, value);
                environmentText.Append(name).Append('=').Append(value).Append('\0');
            }
            environmentText.Append('\0');
            IntPtr environment = Marshal.StringToHGlobalUni(environmentText.ToString());
            try
            {
                STARTUPINFO startupInfo = CreateStartupInfo();
                using (SafeFileHandle input = OpenNullInput())
                using (FileStream output = new FileStream(stdoutLogPath, FileMode.CreateNew, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete))
                using (FileStream error = new FileStream(stderrLogPath, FileMode.CreateNew, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete))
                {
                    startupInfo.hStdInput = input.DangerousGetHandle();
                    startupInfo.hStdOutput = output.SafeFileHandle.DangerousGetHandle();
                    startupInfo.hStdError = error.SafeFileHandle.DangerousGetHandle();
                    return StartProcessWithStreams(executable, startInfo.Arguments, workingDirectory, startupInfo, false, false, environment);
                }
            }
            finally { Marshal.FreeHGlobal(environment); }
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetShortPathName(string longPath, StringBuilder shortPath, uint bufferLength);

        public static string ResolveProcessPath(string path, bool isWorkingDirectory = false, bool preserveExecutableNamespace = false)
        {
            if (string.IsNullOrEmpty(path)) { return path; }
            string logical = LauncherPaths.RemoveWindowsPathNamespace(path);
            if (preserveExecutableNamespace && (isWorkingDirectory || !LauncherPaths.IsAbsoluteFilesystemPath(logical)))
            {
                throw new ArgumentException("Native executable paths must be absolute and cannot be working directories.");
            }
            int prefixLength = preserveExecutableNamespace ? (logical.StartsWith("\\\\", StringComparison.Ordinal) ? 6 : 4) : 0;
            int maximumLength = (!isWorkingDirectory || logical.EndsWith("\\", StringComparison.Ordinal) ? 259 : 258) - prefixLength;
            if (logical.Length <= maximumLength) { return preserveExecutableNamespace ? LauncherPaths.ToNativeFilesystemPath(logical, preservePhysicalName: true) : logical; }
            StringBuilder buffer = new StringBuilder(32768);
            uint length = GetShortPathName(LauncherPaths.ToNativeFilesystemPath(logical), buffer, (uint)buffer.Capacity);
            if (length == 0)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows could not resolve a short physical process path. Use an installation path supported by the host's filesystem and process APIs.");
            }
            string result = buffer.ToString();
            result = LauncherPaths.RemoveWindowsPathNamespace(result);
            prefixLength = preserveExecutableNamespace ? (result.StartsWith("\\\\", StringComparison.Ordinal) ? 6 : 4) : 0;
            maximumLength = (!isWorkingDirectory || result.EndsWith("\\", StringComparison.Ordinal) ? 259 : 258) - prefixLength;
            if (length >= buffer.Capacity || result.Length > maximumLength)
            {
                throw new InvalidOperationException("This long process path has no usable existing short filesystem name. Choose a shorter installation path; SoAI does not change the host's short-name policy.");
            }
            return preserveExecutableNamespace ? LauncherPaths.ToNativeFilesystemPath(result, preservePhysicalName: true) : result;
        }
        private static STARTUPINFO CreateStartupInfo()
        {
            STARTUPINFO startupInfo = new STARTUPINFO();
            startupInfo.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            startupInfo.dwFlags = STARTF_USESHOWWINDOW | STARTF_USESTDHANDLES;
            startupInfo.wShowWindow = 0;
            return startupInfo;
        }

        private static NativeBackendJob StartProcessWithStreams(string executable, string arguments, string workingDirectory, STARTUPINFO startupInfo, bool useConsole, bool allowBreakaway, IntPtr environment = default(IntPtr))
        {
            if (Path.IsPathRooted(executable) && executable.Length >= 260)
            {
                executable = LauncherPaths.ToNativeFilesystemPath(executable);
            }
            workingDirectory = NativeBackendJob.ResolveProcessPath(workingDirectory, true);
            RequireInheritableHandle(startupInfo.hStdInput);
            RequireInheritableHandle(startupInfo.hStdOutput);
            RequireInheritableHandle(startupInfo.hStdError);
            PROCESS_INFORMATION processInfo;
            StringBuilder commandLine = new StringBuilder(BackendProcess.Quote(executable) + " " + arguments);
            uint creationFlags = CREATE_SUSPENDED | CREATE_NO_WINDOW;
            if (useConsole) { creationFlags = CREATE_SUSPENDED; }
            if (environment != IntPtr.Zero) { creationFlags |= 0x00000400; }
            if (!CreateProcess(executable, commandLine, IntPtr.Zero, IntPtr.Zero, true, creationFlags, environment, workingDirectory, ref startupInfo, out processInfo))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to create the administrator backend process.");
            }
            IntPtr job = IntPtr.Zero;
            Process process = null;
            try
            {
                job = CreateJobObject(IntPtr.Zero, null);
                if (job == IntPtr.Zero)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to create the backend rollback job.");
                }
                SetKillOnJobClose(job, true, allowBreakaway);
                if (!AssignProcessToJobObject(job, processInfo.hProcess))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to assign the backend process to its rollback job.");
                }
                process = Process.GetProcessById(processInfo.dwProcessId);
                if (WaitForSingleObject(process.Handle, 0) != WAIT_TIMEOUT)
                {
                    throw new InvalidOperationException("The suspended process exited before its lifetime could be retained.");
                }
                if (ResumeThread(processInfo.hThread) == UInt32.MaxValue)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to resume the backend process.");
                }
                CloseHandle(processInfo.hThread);
                CloseHandle(processInfo.hProcess);
                return new NativeBackendJob(process, job, allowBreakaway);
            }
            catch (Exception startupFailure)
            {
                if (process != null)
                {
                    process.Dispose();
                }
                List<Exception> failures = new List<Exception> { startupFailure };
                try
                {
                    StopIncompleteProcess(processInfo.hProcess, "incomplete backend startup");
                }
                catch (Exception cleanupFailure)
                {
                    failures.Add(cleanupFailure);
                }
                finally
                {
                    CloseHandle(processInfo.hThread);
                    CloseHandle(processInfo.hProcess);
                }
                if (job != IntPtr.Zero)
                {
                    try
                    {
                        TerminateAndWaitForJob(job);
                    }
                    catch (Exception cleanupFailure)
                    {
                        failures.Add(cleanupFailure);
                    }
                    finally
                    {
                        CloseHandle(job);
                    }
                }
                if (failures.Count > 1)
                {
                    throw new AggregateException("Backend startup and process cleanup failed.", failures);
                }
                throw;
            }
        }

        internal static void StopIncompleteProcess(IntPtr process, string subject)
        {
            if (!TerminateProcess(process, 1))
            {
                int error = Marshal.GetLastWin32Error();
                if (WaitForSingleObject(process, 0) != 0)
                {
                    throw new Win32Exception(error, "Failed to stop the " + subject + ".");
                }
            }
            if (WaitForSingleObject(process, 10000) != 0)
            {
                throw new TimeoutException("The " + subject + " did not exit; recovery requires repair.");
            }
        }

        private static void RequireInheritableHandle(IntPtr handle)
        {
            if (!SetHandleInformation(handle, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to prepare hidden backend output handles.");
            }
        }

        private static SafeFileHandle OpenNullInput()
        {
            SafeFileHandle handle = NativeFilesystemHandles.CreateFile("NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
            if (handle.IsInvalid)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to open the hidden backend input device.");
            }
            return handle;
        }

        public void Dispose()
        {
            if (jobHandle == IntPtr.Zero)
            {
                return;
            }
            try
            {
                process.Dispose();
                if (!committed)
                {
                    TerminateAndWaitForJob(jobHandle);
                }
            }
            finally
            {
                CloseHandle(jobHandle);
                jobHandle = IntPtr.Zero;
            }
        }

        private static void TerminateAndWaitForJob(IntPtr job)
        {
            if (!TerminateJobObject(job, 1))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to stop the owned backend job; recovery requires repair.");
            }
            Stopwatch deadline = Stopwatch.StartNew();
            do
            {
                if (CountActiveProcesses(job) == 0)
                {
                    return;
                }
                Thread.Sleep(25);
            }
            while (deadline.Elapsed < TimeSpan.FromSeconds(10));
            throw new TimeoutException("Backend descendants remain active; recovery requires repair.");
        }

        private static uint CountActiveProcesses(IntPtr job)
        {
            JOBOBJECT_BASIC_ACCOUNTING_INFORMATION information;
            if (!QueryInformationJobObject(job, JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION, out information, Marshal.SizeOf(typeof(JOBOBJECT_BASIC_ACCOUNTING_INFORMATION)), IntPtr.Zero))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to verify backend job exit; recovery requires repair.");
            }
            return information.ActiveProcesses;
        }

        private static void SetKillOnJobClose(IntPtr job, bool enabled, bool allowBreakaway)
        {
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION information = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            information.BasicLimitInformation.LimitFlags = (allowBreakaway ? JOB_OBJECT_LIMIT_BREAKAWAY_OK : 0) | (enabled ? JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE : 0);
            int informationLength = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            if (!SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ref information, informationLength))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to configure the backend rollback job.");
            }
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct STARTUPINFO
        {
            public int cb;
            public string lpReserved;
            public string lpDesktop;
            public string lpTitle;
            public int dwX;
            public int dwY;
            public int dwXSize;
            public int dwYSize;
            public int dwXCountChars;
            public int dwYCountChars;
            public int dwFillAttribute;
            public uint dwFlags;
            public short wShowWindow;
            public short cbReserved2;
            public IntPtr lpReserved2;
            public IntPtr hStdInput;
            public IntPtr hStdOutput;
            public IntPtr hStdError;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_INFORMATION
        {
            public IntPtr hProcess;
            public IntPtr hThread;
            public int dwProcessId;
            public int dwThreadId;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct IO_COUNTERS
        {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_BASIC_ACCOUNTING_INFORMATION
        {
            public long TotalUserTime;
            public long TotalKernelTime;
            public long ThisPeriodTotalUserTime;
            public long ThisPeriodTotalKernelTime;
            public uint TotalPageFaultCount;
            public uint TotalProcesses;
            public uint ActiveProcesses;
            public uint TotalTerminatedProcesses;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateProcess(string applicationName, StringBuilder commandLine, IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles, uint creationFlags, IntPtr environment, string currentDirectory, ref STARTUPINFO startupInfo, out PROCESS_INFORMATION processInformation);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateJobObject(IntPtr jobAttributes, string name);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateJobObject(IntPtr job, uint exitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool QueryInformationJobObject(IntPtr job, int informationClass, out JOBOBJECT_BASIC_ACCOUNTING_INFORMATION information, int informationLength, IntPtr returnLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetInformationJobObject(IntPtr job, int informationClass, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION information, int informationLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint ResumeThread(IntPtr thread);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateProcess(IntPtr process, uint exitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetHandleInformation(IntPtr handle, uint mask, uint flags);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool QueryInformationJobObject(IntPtr job, int informationClass, out JOBOBJECT_EXTENDED_LIMIT_INFORMATION information, int informationLength, IntPtr returnLength);

        [DllImport("kernel32.dll")]
        internal static extern IntPtr GetCurrentProcess();

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool IsProcessInJob(IntPtr process, IntPtr job, out bool result);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint desiredAccess, bool inheritHandle, uint processId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool DuplicateHandle(IntPtr sourceProcess, IntPtr sourceHandle, IntPtr targetProcess, out IntPtr targetHandle, uint desiredAccess, bool inheritHandle, uint options);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool QueryFullProcessImageName(IntPtr process, uint flags, StringBuilder imageName, ref int size);

        [DllImport("ntdll.dll")]
        private static extern uint NtQuerySystemInformation(int informationClass, IntPtr information, int informationLength, out int returnLength);
    }

    internal static class BackendProcess
    {
        private const int InstallCommandTimeoutMilliseconds = 18000000;

        public static int PrepareInstallRuntime(LauncherPaths paths, string[] args)
        {
            if (!LauncherCommand.IsInstallCommand(args))
            {
                return 0;
            }
            return RunInstallerSupportScript(paths, delegate(string powershell, string script, string operationDirectory, List<SafeFileHandle> retainedHandles)
            {
                Mutex bootstrapGate = null;
                try
                {
                    bool missingPython = !File.Exists(LauncherPaths.ToNativeFilesystemPath(paths.ResolveStandalonePythonExecutable()));
                    string preflightArguments = "-PreflightOnly";
                    if (missingPython)
                    {
                        string identityPath = Path.Combine(paths.RootDirectory, "release-info-v1.json");
                        RetainInstallPath(identityPath, retainedHandles);
                        RetainInstallPath(Path.Combine(paths.RootDirectory, "VERSION"), retainedHandles);
                        RetainInstallPath(paths.BackendMain, retainedHandles);
                        bootstrapGate = NativeFilesystemHandles.OpenInstallerBootstrapGate(paths.RootDirectory);
                        preflightArguments += " -InstallRoot " + Quote(paths.RootDirectory);
                    }
                    int result = RunInstallPreparation(powershell, script, operationDirectory, preflightArguments, "preflight.log");
                    if (result != 0)
                    {
                        return result;
                    }
                    if (missingPython)
                    {
                        return RunInstallPreparation(
                            powershell, script, operationDirectory,
                            "-BootstrapOnly -InstallRoot " + Quote(paths.RootDirectory)
                                + " -DiagnosticRoot " + Quote(Path.Combine(operationDirectory, "runtime")), "bootstrap.log");
                    }
                    return RunInstallPreparation(
                        powershell, script, operationDirectory,
                        "-VisualCppRuntimeOnly -InstallRoot " + Quote(paths.RootDirectory)
                            + " -DiagnosticRoot " + Quote(Path.Combine(operationDirectory, "runtime")), "visual-cpp-runtime.log");
                }
                finally
                {
                    if (bootstrapGate != null) { bootstrapGate.Dispose(); }
                }
            });
        }

        public static int SecureInstallation(LauncherPaths paths, bool completeInstallation)
        {
            return RunInstallerSupportScript(paths, delegate(string powershell, string script, string operationDirectory, List<SafeFileHandle> retainedHandles)
            {
                return RunInstallPreparation(
                    powershell, script, operationDirectory,
                    "-SecureAccessOnly -InstallRoot " + Quote(paths.RootDirectory)
                        + " -DiagnosticRoot " + Quote(Path.Combine(operationDirectory, "runtime"))
                        + (completeInstallation ? " -CompleteInstallation" : ""), "secure-access.log");
            });
        }

        public static int CompleteInstallation(LauncherPaths paths)
        {
            int exitCode = SecureInstallation(paths, true);
            if (exitCode != 0)
            {
                return exitCode;
            }
            Console.WriteLine(ServiceRegistration.Register(paths.RootDirectory)
                ? "SoAI registered its Windows background service."
                : "SoAI updated its Windows background service.");
            return 0;
        }

        private static int RunInstallerSupportScript(LauncherPaths paths, Func<string, string, string, List<SafeFileHandle>, int> operation)
        {
            if (!PrivilegeState.IsElevated())
            {
                throw new InvalidOperationException("Runtime preparation requires administrator access.");
            }
            string systemRoot = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
            string stagingParent = Path.Combine(systemRoot, "Temp");
            string powershell = Path.Combine(systemRoot, "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
            if (stagingParent.Length > 160 || powershell.Length >= 260 || !File.Exists(powershell))
            {
                throw new InvalidOperationException("Windows runtime preflight requires a usable short system temporary path and native PowerShell host.");
            }
            List<SafeFileHandle> retainedHandles = new List<SafeFileHandle>();
            string operationDirectory = null;
            bool succeeded = false;
            try
            {
                RetainInstallPath(stagingParent, retainedHandles);
                RetainInstallPath(paths.RootDirectory, retainedHandles);
                string scriptSource = Path.Combine(paths.RootDirectory, "installer-support", "Install-SoAIRuntime.ps1");
                string metadataSource = Path.Combine(paths.RootDirectory, "installer-support", "dependencies-v1.json");
                string ownershipSource = Path.Combine(paths.RootDirectory, "installer-support", "Shared-SoAIResourceOwnership.ps1");
                RetainInstallPath(scriptSource, retainedHandles);
                RetainInstallPath(metadataSource, retainedHandles);
                RetainInstallPath(ownershipSource, retainedHandles);
                operationDirectory = CreateInstallOperationDirectory(stagingParent);
                File.WriteAllText(Path.Combine(operationDirectory, "install-root.txt"), paths.RootDirectory, Encoding.UTF8);
                string script = Path.Combine(operationDirectory, "Install-SoAIRuntime.ps1");
                File.Copy(LauncherPaths.ToNativeFilesystemPath(scriptSource), LauncherPaths.ToNativeFilesystemPath(script), false);
                File.Copy(LauncherPaths.ToNativeFilesystemPath(metadataSource), LauncherPaths.ToNativeFilesystemPath(Path.Combine(operationDirectory, "dependencies-v1.json")), false);
                File.Copy(LauncherPaths.ToNativeFilesystemPath(ownershipSource), LauncherPaths.ToNativeFilesystemPath(Path.Combine(operationDirectory, "Shared-SoAIResourceOwnership.ps1")), false);
                int result = operation(powershell, script, operationDirectory, retainedHandles);
                succeeded = result == 0;
                return result;
            }
            catch (Exception exception)
            {
                if (operationDirectory != null)
                {
                    try
                    {
                        File.WriteAllText(Path.Combine(operationDirectory, "preparation-error.txt"), exception.ToString(), Encoding.UTF8);
                    }
                    catch (Exception diagnosticException)
                    {
                        throw new AggregateException("Windows runtime preparation failed and its diagnostic record could not be saved.", exception, diagnosticException);
                    }
                }
                throw;
            }
            finally
            {
                foreach (SafeFileHandle handle in retainedHandles)
                {
                    handle.Dispose();
                }
                if (operationDirectory != null)
                {
                    if (succeeded)
                    {
                        Directory.Delete(operationDirectory, true);
                    }
                    else
                    {
                        Console.Error.WriteLine("Windows runtime preparation evidence: " + operationDirectory);
                    }
                }
            }
        }


        private static int RunInstallPreparation(string powershell, string script, string directory, string arguments, string logName)
        {
            string previousTemp = Environment.GetEnvironmentVariable("TEMP");
            string previousTmp = Environment.GetEnvironmentVariable("TMP");
            try
            {
                Environment.SetEnvironmentVariable("TEMP", directory);
                Environment.SetEnvironmentVariable("TMP", directory);
                using (NativeBackendJob job = NativeBackendJob.StartProcess(
                    powershell, "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File " + Quote(script) + " " + arguments,
                    directory, Path.Combine(directory, logName), false))
                {
                    if (!job.ProcessHandle.WaitForExit(InstallCommandTimeoutMilliseconds))
                    {
                        throw new TimeoutException("Windows runtime preparation exceeded its bounded deadline. Its diagnostic evidence has been retained.");
                    }
                    return job.ExitCode;
                }
            }
            finally
            {
                Environment.SetEnvironmentVariable("TEMP", previousTemp);
                Environment.SetEnvironmentVariable("TMP", previousTmp);
            }
        }

        private static void RetainInstallPath(string path, List<SafeFileHandle> handles)
        {
            string current = Path.GetFullPath(path);
            while (!string.IsNullOrEmpty(current))
            {
                string nativePath = LauncherPaths.ToNativeFilesystemPath(current);
                bool isDirectory = Directory.Exists(nativePath);
                SafeFileHandle handle = OpenInstallPath(nativePath, isDirectory ? 0x80U : 0x81U, isDirectory ? 3U : 1U, IntPtr.Zero, 3, 0x02200000, IntPtr.Zero);
                if (handle.IsInvalid)
                {
                    int errorCode = Marshal.GetLastWin32Error();
                    handle.Dispose();
                    throw new Win32Exception(errorCode, "An installer input or system temporary ancestor cannot be retained safely.");
                }
                INSTALL_PATH_ATTRIBUTES information;
                if (!GetInstallPathAttributes(handle, 9, out information, Marshal.SizeOf(typeof(INSTALL_PATH_ATTRIBUTES)))
                    || (information.Attributes & 0x400) != 0)
                {
                    handle.Dispose();
                    throw new InvalidOperationException("Installer inputs and staging ancestors must not be reparse points.");
                }
                handles.Add(handle);
                current = Path.GetDirectoryName(current);
            }
        }

        private static string CreateInstallOperationDirectory(string parent)
        {
            DirectorySecurity security = new DirectorySecurity();
            security.SetAccessRuleProtection(true, false);
            foreach (WellKnownSidType identity in new WellKnownSidType[] { WellKnownSidType.LocalSystemSid, WellKnownSidType.BuiltinAdministratorsSid })
            {
                security.AddAccessRule(new FileSystemAccessRule(
                    new SecurityIdentifier(identity, null), FileSystemRights.FullControl,
                    InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                    PropagationFlags.None, AccessControlType.Allow));
            }
            byte[] descriptor = security.GetSecurityDescriptorBinaryForm();
            IntPtr nativeDescriptor = Marshal.AllocHGlobal(descriptor.Length);
            try
            {
                Marshal.Copy(descriptor, 0, nativeDescriptor, descriptor.Length);
                INSTALL_DIRECTORY_SECURITY attributes = new INSTALL_DIRECTORY_SECURITY();
                attributes.Length = Marshal.SizeOf(typeof(INSTALL_DIRECTORY_SECURITY));
                attributes.Descriptor = nativeDescriptor;
                for (int attempt = 0; attempt < 3; attempt++)
                {
                    string path = Path.Combine(parent, "SoAI-" + Guid.NewGuid().ToString("N"));
                    if (CreateInstallDirectory(path, ref attributes))
                    {
                        return path;
                    }
                    int error = Marshal.GetLastWin32Error();
                    if (error != 183 || attempt == 2)
                    {
                        throw new Win32Exception(error, "Could not allocate exclusive installer staging.");
                    }
                }
                throw new InvalidOperationException("Installer staging allocation has no result.");
            }
            finally
            {
                Marshal.FreeHGlobal(nativeDescriptor);
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct INSTALL_PATH_ATTRIBUTES
        {
            public uint Attributes;
            public uint ReparseTag;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct INSTALL_DIRECTORY_SECURITY
        {
            public int Length;
            public IntPtr Descriptor;
            public bool Inherit;
        }

        [DllImport("kernel32.dll", EntryPoint = "CreateFileW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern SafeFileHandle OpenInstallPath(string path, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);

        [DllImport("kernel32.dll", EntryPoint = "GetFileInformationByHandleEx", SetLastError = true)]
        private static extern bool GetInstallPathAttributes(SafeFileHandle handle, int informationClass, out INSTALL_PATH_ATTRIBUTES information, int size);

        [DllImport("kernel32.dll", EntryPoint = "CreateDirectoryW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateInstallDirectory(string path, ref INSTALL_DIRECTORY_SECURITY security);

        public static Process StartForeground(LauncherPaths paths, string[] args)
        {
            ProcessStartInfo psi = CreateProcessStartInfo(paths, args);
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            return Process.Start(psi);
        }

        public static void KillQuietly(Process process)
        {
            if (process == null)
            {
                return;
            }
            try
            {
                if (!process.HasExited)
                {
                    process.Kill();
                }
            }
            catch
            {
            }
        }

        public static int RunForeground(LauncherPaths paths, string[] args)
        {
            if (LauncherCommand.IsInstallCommand(args))
            {
                string python = NativeBackendJob.ResolveProcessPath(ResolvePython(paths, args), preserveExecutableNamespace: true);
                RequireBackendMain(paths);
                ConfigureBackendEnvironment(paths);
                using (NativeBackendJob job = NativeBackendJob.StartConsoleProcess(
                    python, Quote(paths.BackendMain) + BuildArgumentString(args), paths.RootDirectory))
                {
                    if (!job.ProcessHandle.WaitForExit(InstallCommandTimeoutMilliseconds))
                    {
                        throw new TimeoutException("Installation exceeded its bounded deadline. Preserve the installation diagnostics before retrying.");
                    }
                    return job.ExitCode;
                }
            }
            Process process = StartForeground(paths, args);
            process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data != null)
                {
                    Console.Out.WriteLine(e.Data);
                }
            };
            process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data != null)
                {
                    Console.Error.WriteLine(e.Data);
                }
            };
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            process.WaitForExit();
            return process.ExitCode;
        }

        private static ProcessStartInfo CreateProcessStartInfo(LauncherPaths paths, string[] args)
        {
            string python = ResolvePython(paths, args);
            if (!File.Exists(LauncherPaths.ToNativeFilesystemPath(python)))
            {
                throw new FileNotFoundException("The bundled Python 3.13 runtime is missing or damaged. Please reinstall SoAI.", python);
            }
            RequireBackendMain(paths);

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = NativeBackendJob.ResolveProcessPath(python, preserveExecutableNamespace: true);
            psi.Arguments = Quote(paths.BackendMain) + BuildArgumentString(args);
            psi.WorkingDirectory = NativeBackendJob.ResolveProcessPath(paths.RootDirectory, true);
            ApplyBackendEnvironment(paths, psi.EnvironmentVariables);
            return psi;
        }

        internal static string ResolvePython(LauncherPaths paths, string[] args)
        {
            return LauncherCommand.IsInstallCommand(args)
                ? paths.ResolveBootstrapPythonExecutable()
                : paths.ResolveLaunchPythonExecutable();
        }

        internal static void RequireBackendMain(LauncherPaths paths)
        {
            if (!File.Exists(LauncherPaths.ToNativeFilesystemPath(paths.BackendMain)))
            {
                throw new FileNotFoundException("SoAI backend entrypoint was not found.", paths.BackendMain);
            }
        }

        internal static void ConfigureBackendEnvironment(LauncherPaths paths)
        {
            ClearInheritedPythonEnvironment();
            Environment.SetEnvironmentVariable("PATH", BuildProcessPath(paths, Environment.GetEnvironmentVariable("PATH")));
            Environment.SetEnvironmentVariable("SOAI_GUI_LAUNCHED", "1");
            Environment.SetEnvironmentVariable("SOAI_NO_BROWSER", "1");
            Environment.SetEnvironmentVariable("PYTHONPATH", paths.BackendDirectory);
            Environment.SetEnvironmentVariable("PYTHONNOUSERSITE", "1");
            Environment.SetEnvironmentVariable("PYTHONUTF8", "1");
            Environment.SetEnvironmentVariable("PYTHONIOENCODING", "utf-8");
        }

        private static void ApplyBackendEnvironment(LauncherPaths paths, System.Collections.Specialized.StringDictionary environment)
        {
            ClearInheritedPythonEnvironment(environment);
            environment["PATH"] = BuildProcessPath(paths, environment["PATH"]);
            environment["SOAI_GUI_LAUNCHED"] = "1";
            environment["SOAI_NO_BROWSER"] = "1";
            environment["PYTHONPATH"] = paths.BackendDirectory;
            environment["PYTHONNOUSERSITE"] = "1";
            environment["PYTHONUTF8"] = "1";
            environment["PYTHONIOENCODING"] = "utf-8";
        }

        private static void ClearInheritedPythonEnvironment()
        {
            List<string> names = new List<string>();
            foreach (string name in Environment.GetEnvironmentVariables().Keys)
            {
                if (name.StartsWith("PYTHON", StringComparison.OrdinalIgnoreCase))
                {
                    names.Add(name);
                }
            }
            foreach (string name in names)
            {
                Environment.SetEnvironmentVariable(name, null);
            }
        }

        private static void ClearInheritedPythonEnvironment(System.Collections.Specialized.StringDictionary environment)
        {
            List<string> names = new List<string>();
            foreach (string name in environment.Keys)
            {
                if (name.StartsWith("PYTHON", StringComparison.OrdinalIgnoreCase))
                {
                    names.Add(name);
                }
            }
            foreach (string name in names)
            {
                environment.Remove(name);
            }
        }

        internal static string BuildProcessPath(LauncherPaths paths, string inheritedPath)
        {
            List<string> parts = new List<string>();
            AddExistingDirectory(parts, paths.RootDirectory);
            AddExistingDirectory(parts, paths.StandalonePythonDirectory);
            AddExistingDirectory(parts, paths.VenvScriptsDirectory);
            if (!string.IsNullOrWhiteSpace(inheritedPath))
            {
                parts.Add(inheritedPath);
            }
            return string.Join(Path.PathSeparator.ToString(), parts.ToArray());
        }

        private static void AddExistingDirectory(List<string> parts, string path)
        {
            if (!string.IsNullOrWhiteSpace(path) && Directory.Exists(LauncherPaths.ToNativeFilesystemPath(path)))
            {
                parts.Add(path);
            }
        }

        internal static string BuildArgumentString(string[] args)
        {
            if (args == null || args.Length == 0)
            {
                return string.Empty;
            }
            StringBuilder builder = new StringBuilder();
            foreach (string arg in args)
            {
                builder.Append(' ');
                builder.Append(Quote(arg ?? string.Empty));
            }
            return builder.ToString();
        }

        internal static string Quote(string value)
        {
            if (value == null)
            {
                value = string.Empty;
            }
            StringBuilder builder = new StringBuilder();
            builder.Append('"');
            int backslashes = 0;
            foreach (char character in value)
            {
                if (character == '\\')
                {
                    backslashes += 1;
                    continue;
                }
                if (character == '"')
                {
                    builder.Append('\\', backslashes * 2 + 1);
                    builder.Append('"');
                    backslashes = 0;
                    continue;
                }
                if (backslashes > 0)
                {
                    builder.Append('\\', backslashes);
                    backslashes = 0;
                }
                builder.Append(character);
            }
            if (backslashes > 0)
            {
                builder.Append('\\', backslashes * 2);
            }
            builder.Append('"');
            return builder.ToString();
        }
    }

    internal static class HealthProbe
    {
        private static readonly TimeSpan ProbeTimeout = TimeSpan.FromMilliseconds(900);

        public static async Task<bool> WaitForReadyAsync(EndpointInfo endpoint, TimeSpan interval, TimeSpan total, CancellationToken token)
        {
            Stopwatch elapsed = Stopwatch.StartNew();
            while (true)
            {
                token.ThrowIfCancellationRequested();
                TimeSpan remaining = total - elapsed.Elapsed;
                if (remaining <= TimeSpan.Zero)
                {
                    return false;
                }
                if (await IsReadyWithinAsync(endpoint, remaining < ProbeTimeout ? remaining : ProbeTimeout, token))
                {
                    return true;
                }
                remaining = total - elapsed.Elapsed;
                if (remaining <= TimeSpan.Zero)
                {
                    return false;
                }
                await Task.Delay(remaining < interval ? remaining : interval, token);
            }
        }

        public static Task<bool> IsReadyAsync(EndpointInfo endpoint, CancellationToken token)
        {
            return IsReadyWithinAsync(endpoint, ProbeTimeout, token);
        }

        private static async Task<bool> IsReadyWithinAsync(EndpointInfo endpoint, TimeSpan timeout, CancellationToken token)
        {
            token.ThrowIfCancellationRequested();
            if (endpoint == null)
            {
                return false;
            }

            try
            {
                int statusCode = await HttpProbe.GetStatusCodeAsync(endpoint.HealthUrl, timeout, token);
                return statusCode == 200;
            }
            catch (OperationCanceledException)
            {
                token.ThrowIfCancellationRequested();
                return false;
            }
            catch (Exception)
            {
                return false;
            }
        }
    }

    internal sealed class EndpointInfo
    {
        public EndpointInfo(string scheme, string host, int port)
        {
            Scheme = (scheme ?? "http").Trim().ToLowerInvariant();
            Host = string.IsNullOrWhiteSpace(host) ? "127.0.0.1" : host.Trim();
            Port = port;
        }

        public string Scheme { get; private set; }
        public string Host { get; private set; }
        public int Port { get; private set; }

        public string BaseUrl
        {
            get
            {
                return Scheme + "://" + Host + ":" + Port.ToString(CultureInfo.InvariantCulture) + "/";
            }
        }

        public string HealthUrl
        {
            get
            {
                return BaseUrl + "api/v1/system/health";
            }
        }

        public string AuthenticationCookieName
        {
            get { return Scheme == "https" ? "__Host-soai-token" : "soai-http-token"; }
        }

        public bool IsSameOrigin(string value)
        {
            Uri uri;
            if (!Uri.TryCreate(value, UriKind.Absolute, out uri) || !LoopbackCertificatePolicy.IsLoopbackUri(uri.AbsoluteUri))
            {
                return false;
            }

            return string.Equals(uri.Scheme, Scheme, StringComparison.OrdinalIgnoreCase)
                && uri.Port == Port;
        }

        public string RebaseAppUri(string value, EndpointInfo previous)
        {
            if (previous == null || !previous.IsSameOrigin(value)) return null;
            Uri source = new Uri(value, UriKind.Absolute);
            UriBuilder destination = new UriBuilder(BaseUrl);
            destination.Path = source.AbsolutePath;
            destination.Query = source.Query.Length == 0 ? string.Empty : source.Query.Substring(1);
            destination.Fragment = source.Fragment.Length == 0 ? string.Empty : source.Fragment.Substring(1);
            return destination.Uri.AbsoluteUri;
        }

        public bool IsTransportChangeUri(string value)
        {
            Uri destination;
            return Uri.TryCreate(value, UriKind.Absolute, out destination)
                && LoopbackCertificatePolicy.IsLoopbackUri(value)
                && destination.UserInfo.Length == 0
                && destination.Port == Port
                && (destination.Scheme == "http" || destination.Scheme == "https")
                && destination.Scheme != Scheme;
        }
    }

    internal static class DiscoveryProbe
    {
        static DiscoveryProbe()
        {
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
        }

        private static readonly int[] Ports = new int[]
        {
            7950,
            7951,
            7952,
            7953,
            7954,
            7955,
            7956,
            7957,
            7958,
            7959,
            7960
        };

        private static readonly TimeSpan DiscoveryProbeTimeout = TimeSpan.FromMilliseconds(650);
        private static readonly string[] Schemes = new string[] { "http", "https" };
        private static readonly string[] Hosts = new string[] { "127.0.0.1", "localhost" };
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer();

        public static async Task<EndpointInfo> WaitForEndpointAsync(TimeSpan interval, TimeSpan total, CancellationToken token)
        {
            token.ThrowIfCancellationRequested();
            if (total <= TimeSpan.Zero)
            {
                return null;
            }
            using (CancellationTokenSource deadline = CancellationTokenSource.CreateLinkedTokenSource(token))
            {
                deadline.CancelAfter(total);
                while (!deadline.IsCancellationRequested)
                {
                    EndpointInfo endpoint;
                    try
                    {
                        endpoint = await TryResolveAsync(deadline.Token);
                    }
                    catch (OperationCanceledException)
                    {
                        if (!deadline.IsCancellationRequested)
                        {
                            throw;
                        }
                        token.ThrowIfCancellationRequested();
                        return null;
                    }
                    if (endpoint != null)
                    {
                        token.ThrowIfCancellationRequested();
                        if (deadline.IsCancellationRequested)
                        {
                            return null;
                        }
                        return endpoint;
                    }
                    token.ThrowIfCancellationRequested();
                    if (deadline.IsCancellationRequested)
                    {
                        return null;
                    }
                    try
                    {
                        await Task.Delay(interval, deadline.Token);
                    }
                    catch (OperationCanceledException)
                    {
                        if (!deadline.IsCancellationRequested)
                        {
                            throw;
                        }
                        break;
                    }
                }
                token.ThrowIfCancellationRequested();
                return null;
            }
        }

        public static async Task<EndpointInfo> TryResolveAsync(CancellationToken token)
        {
            token.ThrowIfCancellationRequested();
            using (CancellationTokenSource attempt = CancellationTokenSource.CreateLinkedTokenSource(token))
            {
                int probeCount = Hosts.Length * Ports.Length * Schemes.Length;
                List<Task<EndpointInfo>> allProbes = new List<Task<EndpointInfo>>(probeCount);
                EndpointInfo selectedEndpoint = null;
                ExceptionDispatchInfo launchFailure = null;
                try
                {
                    foreach (string host in Hosts)
                    {
                        foreach (int port in Ports)
                        {
                            foreach (string scheme in Schemes)
                            {
                                Task<EndpointInfo> probe = ProbeOneAsync(scheme, host, port, attempt.Token);
                                allProbes.Add(probe);
                            }
                        }
                    }

                    // Launch concurrently, but select in a stable host/port order. Racing
                    // localhost against 127.0.0.1 changes the WebView cookie origin.
                    foreach (Task<EndpointInfo> probe in allProbes)
                    {
                        EndpointInfo result = await probe;
                        if (result != null)
                        {
                            selectedEndpoint = result;
                            break;
                        }
                    }
                }
                catch (Exception exception)
                {
                    launchFailure = ExceptionDispatchInfo.Capture(exception);
                }
                attempt.Cancel();
                await Task.WhenAll(allProbes);
                token.ThrowIfCancellationRequested();
                if (launchFailure != null)
                {
                    launchFailure.Throw();
                }
                return selectedEndpoint;
            }
        }

        private static async Task<EndpointInfo> ProbeOneAsync(string discoveryScheme, string host, int discoveryPort, CancellationToken token)
        {
            try
            {
                string url = discoveryScheme + "://" + host + ":" + discoveryPort.ToString(CultureInfo.InvariantCulture) + "/";
                string json = await HttpProbe.GetStringAsync(url, DiscoveryProbeTimeout, token);
                return ParseEndpoint(json, host);
            }
            catch (OperationCanceledException)
            {
                return null;
            }
            catch
            {
                return null;
            }
        }

        private static EndpointInfo ParseEndpoint(string json, string discoveryHost)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return null;
            }

            Dictionary<string, object> payload = Serializer.Deserialize<Dictionary<string, object>>(json);
            if (payload == null)
            {
                return null;
            }

            object portValue;
            object schemeValue;
            if (!payload.TryGetValue("port", out portValue) || !payload.TryGetValue("scheme", out schemeValue))
            {
                return null;
            }

            int port = Convert.ToInt32(portValue, CultureInfo.InvariantCulture);
            string scheme = Convert.ToString(schemeValue, CultureInfo.InvariantCulture);
            if (port <= 0 || port > 65535)
            {
                return null;
            }
            if (!string.Equals(scheme, "http", StringComparison.OrdinalIgnoreCase)
                && !string.Equals(scheme, "https", StringComparison.OrdinalIgnoreCase))
            {
                return null;
            }

            return new EndpointInfo(scheme, discoveryHost, port);
        }
    }

    internal static class HttpProbe
    {
        public static Task<string> GetStringAsync(string url, TimeSpan timeout, CancellationToken token)
        {
            return ExecuteAsync(url, timeout, token, ReadSuccessfulBodyAsync);
        }

        public static Task<int> GetStatusCodeAsync(string url, TimeSpan timeout, CancellationToken token)
        {
            return ExecuteAsync(url, timeout, token, ReadStatusCode);
        }

        private static async Task<T> ExecuteAsync<T>(string url, TimeSpan timeout, CancellationToken token, Func<HttpWebResponse, Task<T>> readResponse)
        {
            token.ThrowIfCancellationRequested();
            if (timeout <= TimeSpan.Zero)
            {
                throw new TimeoutException("The local SoAI probe had no remaining time.");
            }
            HttpWebRequest request = CreateRequest(url, timeout);
            using (CancellationTokenSource timed = CancellationTokenSource.CreateLinkedTokenSource(token))
            {
                timed.CancelAfter(timeout);
                using (timed.Token.Register(delegate { request.Abort(); }))
                {
                    try
                    {
                        using (HttpWebResponse response = await ReceiveResponseAsync(request))
                        {
                            T result = await readResponse(response);
                            timed.Token.ThrowIfCancellationRequested();
                            return result;
                        }
                    }
                    catch (Exception exception)
                    {
                        if (token.IsCancellationRequested)
                        {
                            throw new OperationCanceledException(token);
                        }
                        if (timed.IsCancellationRequested)
                        {
                            throw new TimeoutException("The local SoAI probe did not finish in time.", exception);
                        }
                        throw;
                    }
                }
            }
        }

        private static async Task<HttpWebResponse> ReceiveResponseAsync(HttpWebRequest request)
        {
            try
            {
                return (HttpWebResponse)await request.GetResponseAsync();
            }
            catch (WebException exception)
            {
                HttpWebResponse response = exception.Response as HttpWebResponse;
                if (exception.Status == WebExceptionStatus.ProtocolError && response != null)
                {
                    return response;
                }
                if (exception.Response != null)
                {
                    exception.Response.Dispose();
                }
                throw;
            }
        }

        private static async Task<string> ReadSuccessfulBodyAsync(HttpWebResponse response)
        {
            if (response.StatusCode != HttpStatusCode.OK)
            {
                return null;
            }
            using (Stream stream = response.GetResponseStream())
            using (StreamReader reader = new StreamReader(stream ?? Stream.Null, Encoding.UTF8))
            {
                return await reader.ReadToEndAsync();
            }
        }

        private static Task<int> ReadStatusCode(HttpWebResponse response)
        {
            return Task.FromResult((int)response.StatusCode);
        }

        private static HttpWebRequest CreateRequest(string url, TimeSpan timeout)
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
            Uri requestUri = request.RequestUri;
            int timeoutMs = (int)Math.Ceiling(timeout.TotalMilliseconds);
            request.Method = "GET";
            request.Accept = "application/json,*/*";
            request.Timeout = timeoutMs;
            request.ReadWriteTimeout = timeoutMs;
            request.KeepAlive = false;
            request.AllowAutoRedirect = false;
            request.ServerCertificateValidationCallback = delegate(object sender, X509Certificate certificate, X509Chain chain, SslPolicyErrors sslPolicyErrors)
            {
                return LoopbackCertificatePolicy.AcceptsCertificate(requestUri, sslPolicyErrors);
            };
            if (LoopbackCertificatePolicy.IsLoopbackUri(requestUri.AbsoluteUri))
            {
                request.Proxy = null;
            }
            return request;
        }
    }

    internal static class LauncherDiagnostics
    {
        private const int BackendOutputLimitBytes = 32768;

        private static string StartupFailurePath
        {
            get { return Path.Combine(LauncherPaths.UserStateDirectory, "launcher-startup-error.txt"); }
        }

        public static string ServiceLogPath(LauncherPaths paths)
        {
            return Path.Combine(paths.RootDirectory, "data", "logs", "soai-service.log");
        }

        public static void ClearStartupFailure()
        {
            try
            {
                if (File.Exists(StartupFailurePath))
                {
                    File.Delete(StartupFailurePath);
                }
            }
            catch
            {
            }
        }

        public static string WriteStartupFailure(LauncherPaths paths, Exception exception)
        {
            try
            {
                string path = StartupFailurePath;
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                StringBuilder builder = new StringBuilder();
                builder.AppendLine("SoAI launcher startup failure");
                builder.AppendLine();
                builder.AppendLine("Install root:");
                if (paths == null)
                {
                    builder.AppendLine("Unresolved: the launcher failed before it verified its program file and installation folder.");
                }
                else
                {
                    builder.AppendLine(paths.RootDirectory ?? string.Empty);
                    builder.AppendLine();
                    builder.AppendLine("Backend entrypoint:");
                    builder.AppendLine(paths.BackendMain ?? string.Empty);
                    builder.AppendLine();
                    builder.AppendLine("Python runtime:");
                    builder.AppendLine(paths.StandalonePythonDirectory ?? string.Empty);
                    builder.AppendLine();
                    builder.AppendLine("Managed Python scripts:");
                    builder.AppendLine(paths.VenvScriptsDirectory ?? string.Empty);
                    builder.AppendLine();
                    builder.AppendLine("Service diagnostics:");
                    builder.AppendLine(ServiceLogPath(paths));
                }
                builder.AppendLine();
                builder.AppendLine("Exception:");
                builder.AppendLine(exception == null ? "Unknown startup failure." : exception.ToString());
                if (File.Exists(path))
                {
                    builder.Insert(0, Environment.NewLine);
                }
                File.AppendAllText(path, builder.ToString(), Encoding.UTF8);
                return path;
            }
            catch
            {
                return string.Empty;
            }
        }

        internal static string ReadLogTail(string path)
        {
            if (!File.Exists(path))
            {
                return "The backend output log was not created.";
            }
            using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                long offset = Math.Max(0, stream.Length - BackendOutputLimitBytes);
                stream.Seek(offset, SeekOrigin.Begin);
                byte[] buffer = new byte[(int)(stream.Length - offset)];
                int totalRead = 0;
                while (totalRead < buffer.Length)
                {
                    int bytesRead = stream.Read(buffer, totalRead, buffer.Length - totalRead);
                    if (bytesRead == 0)
                    {
                        break;
                    }
                    totalRead += bytesRead;
                }
                return Encoding.UTF8.GetString(buffer, 0, totalRead).Trim();
            }
        }
    }

    public sealed class LauncherPaths
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetLongPathName(string shortPath, StringBuilder longPath, uint bufferLength);

        public static string RemoveWindowsPathNamespace(string path)
        {
            string logical = path.StartsWith("\\\\?\\UNC\\", StringComparison.OrdinalIgnoreCase)
                ? "\\\\" + path.Substring(8)
                : path.StartsWith("\\\\?\\", StringComparison.Ordinal) ? path.Substring(4) : path;
            if (path.StartsWith("\\\\?\\", StringComparison.Ordinal) && !IsAbsoluteFilesystemPath(logical))
            {
                throw new ArgumentException("Extended filesystem paths must be absolute drive or UNC paths.");
            }
            return logical;
        }

        internal static bool IsAbsoluteFilesystemPath(string path)
        {
            string filesystemRoot = Path.GetPathRoot(path);
            return !string.IsNullOrEmpty(filesystemRoot) && (filesystemRoot.StartsWith("\\\\", StringComparison.Ordinal)
                || (filesystemRoot.Length == 3 && filesystemRoot[1] == ':' && (filesystemRoot[2] == '\\' || filesystemRoot[2] == '/')));
        }

        internal static string ToNativeFilesystemPath(string path, bool preservePhysicalName = false)
        {
            string absolute = preservePhysicalName ? path : Path.GetFullPath(path);
            if (preservePhysicalName && !IsAbsoluteFilesystemPath(absolute)) { throw new ArgumentException("Physical filesystem names must be absolute."); }
            if (absolute.StartsWith("\\\\?\\", StringComparison.Ordinal)) { return absolute; }
            return absolute.StartsWith("\\\\", StringComparison.Ordinal)
                ? "\\\\?\\UNC\\" + absolute.Substring(2) : "\\\\?\\" + absolute;
        }

        public string RootDirectory { get; private set; }
        public string BackendDirectory { get; private set; }
        public string BackendMain { get; private set; }
        public string FaviconPath { get; private set; }
        public string AppIconPath { get; private set; }
        public string LogoPath { get; private set; }
        public string LightLogoPath { get; private set; }
        public string FrontendDirectory { get; private set; }
        public string StandalonePythonDirectory { get; private set; }
        public string VenvScriptsDirectory { get; private set; }

        public static string UserStateDirectory
        {
            get
            {
                string localApplicationData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                if (!IsAbsoluteFilesystemPath(localApplicationData))
                {
                    throw new InvalidOperationException("The Windows local application data folder is unavailable for this account.");
                }
                return Path.Combine(localApplicationData, "SoAI");
            }
        }

        public static string StableRootIdentity(string rootDirectory)
        {
            byte[] input = Encoding.UTF8.GetBytes(Path.GetFullPath(rootDirectory).TrimEnd('\\').ToUpperInvariant());
            using (System.Security.Cryptography.SHA256 algorithm = System.Security.Cryptography.SHA256.Create())
            {
                byte[] digest = algorithm.ComputeHash(input);
                StringBuilder builder = new StringBuilder(32);
                for (int index = 0; index < 16; index++)
                {
                    builder.Append(digest[index].ToString("x2", CultureInfo.InvariantCulture));
                }
                return builder.ToString();
            }
        }

        public static LauncherPaths FromExecutable()
        {
            return FromRoot(AppDomain.CurrentDomain.BaseDirectory);
        }

        public static LauncherPaths FromRoot(string directory)
        {
            string root = Path.GetFullPath(directory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            StringBuilder buffer = new StringBuilder(32768);
            uint length = GetLongPathName(ToNativeFilesystemPath(root), buffer, (uint)buffer.Capacity);
            if (length == 0 || length >= buffer.Capacity)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "The launcher installation directory cannot be resolved to its real filesystem path.");
            }
            root = buffer.ToString();
            root = RemoveWindowsPathNamespace(root);
            LauncherPaths paths = new LauncherPaths();
            paths.RootDirectory = root;
            paths.BackendDirectory = Path.Combine(root, "backend");
            paths.BackendMain = Path.Combine(paths.BackendDirectory, "main.py");
            paths.FaviconPath = Path.Combine(root, "frontend", "favicon.ico");
            paths.AppIconPath = Path.Combine(root, "soai-app.ico");
            paths.FrontendDirectory = Path.Combine(root, "frontend");
            paths.LogoPath = Path.Combine(paths.FrontendDirectory, "assets", "img", "soai", "soai-logo-dark.png");
            paths.LightLogoPath = Path.Combine(paths.FrontendDirectory, "assets", "img", "soai", "soai-logo-light.png");
            paths.StandalonePythonDirectory = Path.Combine(root, "python");
            paths.VenvScriptsDirectory = Path.Combine(root, "soai_main_venv", "Scripts");
            return paths;
        }

        public static LauncherPaths ForAssetDirectory(string directory)
        {
            LauncherPaths paths = new LauncherPaths();
            paths.RootDirectory = directory;
            paths.FaviconPath = Path.Combine(directory, "soai-app.ico");
            paths.AppIconPath = Path.Combine(directory, "soai-app.ico");
            paths.LogoPath = Path.Combine(directory, "soai-logo-dark.png");
            paths.LightLogoPath = Path.Combine(directory, "soai-logo-light.png");
            return paths;
        }

        public string ResolveLaunchPythonExecutable()
        {
            ResolveBootstrapPythonExecutable();

            string venvPath = Path.Combine(RootDirectory, "soai_main_venv");
            string venvPython = Path.Combine(RootDirectory, "soai_main_venv", "Scripts", "python.exe");
            if (!Directory.Exists(ToNativeFilesystemPath(venvPath)) || !File.Exists(ToNativeFilesystemPath(venvPython)))
            {
                throw new InvalidOperationException("The SoAI managed Python environment is missing or incomplete. Please reinstall SoAI.");
            }

            if (!IsUsablePythonExecutable(venvPython))
            {
                throw new InvalidOperationException("The SoAI managed Python environment is damaged. Please reinstall SoAI.");
            }
            return venvPython;
        }

        internal NativeImageAllowance ManagedRuntimeReadinessAllowance(TimeSpan ordinary)
        {
            return NativeImageBudget.Calculate(
                ordinary.TotalSeconds,
                new string[] { StandalonePythonDirectory, Path.Combine(RootDirectory, "soai_main_venv") },
                new string[0],
                new string[0],
                0);
        }

        internal string ResolveStopPythonExecutable()
        {
            string python = Path.Combine(VenvScriptsDirectory, "python.exe");
            uint attributes = NativeFilesystemHandles.GetFileAttributes(ToNativeFilesystemPath(python));
            if (attributes == uint.MaxValue || (attributes & 0x410) != 0)
            {
                throw new InvalidOperationException("The installed stop runtime is missing, inaccessible, or not a regular file. Repair SoAI with its installer, then retry stop.");
            }
            return python;
        }

        public string ResolveBootstrapPythonExecutable()
        {
            string bootstrapPython = ResolveStandalonePythonExecutable();
            if (!File.Exists(ToNativeFilesystemPath(bootstrapPython)) || !IsUsablePythonExecutable(bootstrapPython))
            {
                throw new FileNotFoundException("The bundled Python 3.13 runtime is missing or damaged. Please reinstall SoAI.", bootstrapPython);
            }
            return bootstrapPython;
        }

        internal string ResolveStandalonePythonExecutable()
        {
            string[] candidates = new string[]
            {
                Path.Combine(RootDirectory, "python", "python.exe"),
                Path.Combine(RootDirectory, "python-3.13", "python.exe"),
                Path.Combine(RootDirectory, "runtime", "python", "python.exe"),
                Path.Combine(RootDirectory, "runtime", "python-3.13", "python.exe"),
                Path.Combine(RootDirectory, "soai_python", "python.exe")
            };

            foreach (string candidate in candidates)
            {
                if (File.Exists(ToNativeFilesystemPath(candidate)))
                {
                    return candidate;
                }
            }
            return candidates[0];
        }

        private static bool IsUsablePythonExecutable(string python)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = NativeBackendJob.ResolveProcessPath(python, preserveExecutableNamespace: true);
                psi.Arguments = "--version";
                psi.WorkingDirectory = NativeBackendJob.ResolveProcessPath(Path.GetDirectoryName(python) ?? Environment.CurrentDirectory, true);
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
                using (Process process = Process.Start(psi))
                {
                    if (process == null)
                    {
                        return false;
                    }
                    if (!process.WaitForExit(5000))
                    {
                        BackendProcess.KillQuietly(process);
                        return false;
                    }
                    string output = (process.StandardOutput.ReadToEnd() + Environment.NewLine + process.StandardError.ReadToEnd()).Trim();
                    return process.ExitCode == 0 && output.IndexOf("Python 3.13", StringComparison.OrdinalIgnoreCase) >= 0;
                }
            }
            catch
            {
                return false;
            }
        }

        public string ResolveWebView2RuntimeDirectory()
        {
            string[] candidates = new string[]
            {
                Path.Combine(RootDirectory, "webview2"),
                Path.Combine(RootDirectory, "WebView2"),
                Path.Combine(RootDirectory, "runtime", "webview2"),
                Path.Combine(RootDirectory, "Microsoft.WebView2.FixedVersionRuntime.149.0.4022.98.x64")
            };

            foreach (string candidate in candidates)
            {
                string resolved = ResolveWebView2ExecutableFolder(candidate);
                if (!string.IsNullOrWhiteSpace(resolved))
                {
                    return resolved;
                }
            }
            return string.Empty;
        }

        private static string ResolveWebView2ExecutableFolder(string candidate)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(candidate) || !Directory.Exists(candidate))
                {
                    return string.Empty;
                }
                if (File.Exists(Path.Combine(candidate, "msedgewebview2.exe")))
                {
                    return candidate;
                }

                foreach (string directory in Directory.GetDirectories(candidate, "Microsoft.WebView2.FixedVersionRuntime.*", SearchOption.TopDirectoryOnly))
                {
                    if (File.Exists(Path.Combine(directory, "msedgewebview2.exe")))
                    {
                        return directory;
                    }
                }

                foreach (string directory in Directory.GetDirectories(candidate, "*", SearchOption.TopDirectoryOnly))
                {
                    if (File.Exists(Path.Combine(directory, "msedgewebview2.exe")))
                    {
                        return directory;
                    }
                }
            }
            catch
            {
            }
            return string.Empty;
        }

        public Icon TryLoadIcon()
        {
            try
            {
                if (File.Exists(AppIconPath))
                {
                    return new Icon(AppIconPath);
                }
                if (File.Exists(FaviconPath))
                {
                    return new Icon(FaviconPath);
                }
            }
            catch
            {
            }
            return SystemIcons.Application;
        }

        public Image TryLoadLogo(bool light)
        {
            try
            {
                string path = light ? LightLogoPath : LogoPath;
                if (File.Exists(path))
                {
                    return Image.FromFile(path);
                }
            }
            catch
            {
            }
            return null;
        }
    }

    internal static class NativeConsole
    {
        private const int ATTACH_PARENT_PROCESS = -1;

        public static void UseStrictUtf8StandardStreams()
        {
            UTF8Encoding commandEncoding = new UTF8Encoding(false, true);
            Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), commandEncoding) { AutoFlush = true });
            Console.SetError(new StreamWriter(Console.OpenStandardError(), commandEncoding) { AutoFlush = true });
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AttachConsole(int dwProcessId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AllocConsole();

        public static void AttachOrCreate()
        {
            if (!AttachConsole(ATTACH_PARENT_PROCESS))
            {
                AllocConsole();
            }
        }
    }

    internal static class PrivilegeState
    {
        public static bool IsElevated()
        {
            try
            {
                WindowsIdentity identity = WindowsIdentity.GetCurrent();
                WindowsPrincipal principal = new WindowsPrincipal(identity);
                return principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
            catch
            {
                return false;
            }
        }

        public static int RunElevatedConsoleCommand(string[] args, PublicStopDeadline stopDeadline)
        {
            try
            {
                ProcessStartInfo startInfo = new ProcessStartInfo();
                startInfo.FileName = NativeBackendJob.ResolveProcessPath(NativeBackendJob.ReadProcessImagePath(NativeBackendJob.GetCurrentProcess()));
                startInfo.Arguments = stopDeadline == null ? LauncherCommand.BuildElevatedConsoleHandoffArguments(args) : stopDeadline.ElevationArguments(args);
                startInfo.WorkingDirectory = NativeBackendJob.ResolveProcessPath(AppDomain.CurrentDomain.BaseDirectory, true);
                startInfo.UseShellExecute = true;
                startInfo.Verb = "runas";
                Process process;
                if (stopDeadline == null) { process = Process.Start(startInfo); }
                else
                {
                    Task<Process> start = Task.Run(delegate { return Process.Start(startInfo); });
                    if (Task.WaitAny(new Task[] { start }, stopDeadline.RemainingMilliseconds) < 0)
                    {
                        start.ContinueWith(delegate(Task<Process> completed)
                        {
                            if (completed.IsFaulted) { AggregateException observed = completed.Exception; }
                            else if (completed.Result != null) { completed.Result.Dispose(); }
                        }, TaskScheduler.Default);
                        string reference = LauncherDiagnostics.WriteStartupFailure(LauncherPaths.FromExecutable(), new TimeoutException("Administrator launch exceeded the public stop deadline."));
                        stopDeadline.WriteFailure("SoAI stop exceeded its deadline while waiting for administrator access. Diagnostic reference: " + reference);
                        return 1;
                    }
                    process = start.GetAwaiter().GetResult();
                }
                if (process == null)
                {
                    return 1;
                }
                try
                {
                    if (stopDeadline != null && !process.WaitForExit(stopDeadline.RemainingMilliseconds))
                    {
                        string reference = LauncherDiagnostics.WriteStartupFailure(LauncherPaths.FromExecutable(), new TimeoutException("Administrator completion exceeded the public stop deadline."));
                        stopDeadline.WriteFailure("SoAI stop did not finish within its public completion budget while waiting for administrator completion. Diagnostic reference: " + reference);
                        return 1;
                    }
                    if (stopDeadline == null) { process.WaitForExit(); }
                    return process.ExitCode;
                }
                finally
                {
                    process.Dispose();
                }
            }
            catch (Win32Exception exception)
            {
                if (exception.NativeErrorCode == 1223)
                {
                    if (stopDeadline == null) { Console.Error.WriteLine("Administrator access was cancelled."); }
                    else { stopDeadline.WriteFailure("Administrator access was cancelled."); }
                    return 1;
                }
                if (stopDeadline == null) { Console.Error.WriteLine("Failed to start the administrator command: " + exception.Message); }
                else
                {
                    string reference = LauncherDiagnostics.WriteStartupFailure(LauncherPaths.FromExecutable(), exception);
                    stopDeadline.WriteFailure("Windows could not grant administrator access for stop. Check permissions and retry. Diagnostic reference: " + reference);
                }
                return 1;
            }
        }
    }

    internal static class LoopbackCertificatePolicy
    {
        private static bool installed;
        private static RemoteCertificateValidationCallback previousCallback;

        public static void Install()
        {
            if (installed)
            {
                return;
            }

            previousCallback = ServicePointManager.ServerCertificateValidationCallback;
            ServicePointManager.ServerCertificateValidationCallback = ValidateServerCertificate;
            installed = true;
        }

        public static bool IsLoopbackUri(string value)
        {
            Uri uri;
            return Uri.TryCreate(value, UriKind.Absolute, out uri) && IsLoopbackHost(uri.Host);
        }

        public static bool AcceptsCertificate(Uri requestUri, SslPolicyErrors sslPolicyErrors)
        {
            if (sslPolicyErrors == SslPolicyErrors.None)
            {
                return true;
            }

            return requestUri != null && IsLoopbackHost(requestUri.Host);
        }

        private static bool ValidateServerCertificate(object sender, X509Certificate certificate, X509Chain chain, SslPolicyErrors sslPolicyErrors)
        {
            HttpWebRequest request = sender as HttpWebRequest;
            if (AcceptsCertificate(request == null ? null : request.Address, sslPolicyErrors))
            {
                return true;
            }

            return previousCallback != null && previousCallback(sender, certificate, chain, sslPolicyErrors);
        }

        private static bool IsLoopbackHost(string host)
        {
            if (string.IsNullOrWhiteSpace(host))
            {
                return false;
            }

            return string.Equals(host, "localhost", StringComparison.OrdinalIgnoreCase)
                || string.Equals(host, "127.0.0.1", StringComparison.OrdinalIgnoreCase)
                || string.Equals(host, "::1", StringComparison.OrdinalIgnoreCase)
                || string.Equals(host, "[::1]", StringComparison.OrdinalIgnoreCase);
        }
    }
}
