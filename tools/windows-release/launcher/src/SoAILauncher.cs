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
            args = LauncherCommand.NormalizeCompleteInstallArguments(args);
            if (args.Length > 0 && string.Equals(args[0], "--recover-install-lock", StringComparison.Ordinal))
            {
                try
                {
                    UTF8Encoding commandEncoding = new UTF8Encoding(false, true);
                    Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), commandEncoding) { AutoFlush = true });
                    Console.SetError(new StreamWriter(Console.OpenStandardError(), commandEncoding) { AutoFlush = true });
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
            LauncherPaths paths = LauncherPaths.FromExecutable();
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
            if (ElevatedBackendHelper.IsHelperCommand(args))
            {
                return ElevatedBackendHelper.Run(paths, args);
            }
            if (LauncherCommand.IsElevatedConsoleHandoff(args))
            {
                if (!PrivilegeState.IsElevated())
                {
                    return 1;
                }
                try
                {
                    string[] commandArguments = LauncherCommand.RemoveElevatedConsoleHandoff(args);
                    int preparationExit = BackendProcess.PrepareInstallRuntime(paths, commandArguments);
                    return preparationExit == 0 ? BackendProcess.RunForeground(paths, commandArguments) : preparationExit;
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
                    return PrivilegeState.RunElevatedConsoleCommand(args);
                }
                try
                {
                    int preparationExit = BackendProcess.PrepareInstallRuntime(paths, args);
                    return preparationExit == 0 ? BackendProcess.RunForeground(paths, args) : preparationExit;
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
            try
            {
                if (UpdateRecovery.TryHandoff(paths, args))
                {
                    return 0;
                }
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                MessageBox.Show("SoAI could not recover the interrupted update. Your recovery files have been retained. Close other SoAI windows and try again. If recovery still fails, keep the installation for repair.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
            if (PrivilegeState.IsElevated())
            {
                if (UnelevatedLauncher.IsHandoffCommand(args))
                {
                    MessageBox.Show("SoAI could not enter the standard desktop session. Start SoAI from its desktop shortcut.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return 1;
                }
                return UnelevatedLauncher.TryLaunch(paths, args) ? 0 : 1;
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
            return RunDesktop(paths, args);
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static int RunDesktop(LauncherPaths paths, string[] args)
        {
            LoopbackCertificatePolicy.Install();
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (LauncherForm form = new LauncherForm(paths, args))
            {
                Application.Run(form);
                return form.ExitCode;
            }
        }
    }

    internal static class UpdateRecovery
    {
        private static readonly int RecoveryProcessTimeoutMilliseconds = (int)TimeSpan.FromMinutes(30).TotalMilliseconds;

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

        public static bool TryHandoff(LauncherPaths paths, string[] args)
        {
            string[] transactions = Directory.GetFileSystemEntries(paths.RootDirectory, ".soai_update_transaction_*");
            if (transactions.Length == 0
                && Directory.GetFileSystemEntries(paths.RootDirectory, ".soai_update_cleanup_*").Length == 0)
            {
                return false;
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
                return false;
            }
            string transactionPath = restorations[0];
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
                string[] relaunchArguments = UnelevatedLauncher.CompleteHandoff(args);
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
                            return true;
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
        private const string AfterUpdateArgument = "--soai-after-update";

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
        private readonly string[] originalArgs;
        private readonly bool afterUpdate;
        private readonly SplashView splash;
        private readonly WebView2 webView;
        private readonly CancellationTokenSource shutdownToken;
        private readonly List<DetachedWebViewForm> detachedWindows;
        private CoreWebView2Environment webViewEnvironment;
        private EndpointInfo activeEndpoint;
        private ElevatedBackendSession backendSession;
        private LauncherAppearance appearance;
        private bool lightTheme;
        private TaskCompletionSource<bool> frontendRevealed;
        private bool closeRequested;
        private bool startupWindowRevealed;
        private string updateHandoffVersion;

        public int ExitCode { get; private set; }

        public LauncherForm(LauncherPaths paths, string[] args)
        {
            this.paths = paths;
            this.afterUpdate = LauncherCommand.IsAfterUpdateLaunch(args);
            this.originalArgs = LauncherCommand.RemoveAfterUpdateArgument(args);
            this.shutdownToken = new CancellationTokenSource();
            this.detachedWindows = new List<DetachedWebViewForm>();
            this.ExitCode = 0;
            this.appearance = LauncherAppearance.Load(paths.StateDirectory);
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
            this.Shown += async delegate { await StartAsync(); };
        }

        private async Task StartAsync()
        {
            try
            {
                LauncherDiagnostics.ClearStartupFailure(paths);
                splash.SetStatus(afterUpdate ? FinishingUpdateStatus : "Preparing the app window...");
                await EnsureWebViewAsync();
                if (afterUpdate)
                {
                    await webView.CoreWebView2.Profile.ClearBrowsingDataAsync(CoreWebView2BrowsingDataKinds.DiskCache);
                }

                splash.SetStatus(afterUpdate ? FinishingUpdateStatus : "Starting SoAI...");
                EndpointInfo endpoint = await EnsureBackendAsync(shutdownToken.Token);
                activeEndpoint = endpoint;

                splash.SetStatus(afterUpdate ? FinishingUpdateStatus : "Preparing the app window...");
                await NavigateAndRevealAsync(endpoint, shutdownToken.Token);
            }
            catch (OperationCanceledException)
            {
                ExitCode = 0;
                if (!closeRequested)
                {
                    CloseQuietly();
                }
            }
            catch (Exception ex)
            {
                ExitCode = 1;
                string diagnosticPath = LauncherDiagnostics.WriteStartupFailure(paths, ex);
                RevealStartupWindow();
                splash.ShowFailure(BuildStartupFailureMessage(ex, diagnosticPath));
            }
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

        private async Task<EndpointInfo> EnsureBackendAsync(CancellationToken token)
        {
            EndpointInfo existingEndpoint = await DiscoveryProbe.WaitForEndpointAsync(TimeSpan.FromMilliseconds(250), TimeSpan.FromSeconds(1), token);
            if (existingEndpoint != null && await HealthProbe.WaitForReadyAsync(existingEndpoint, TimeSpan.FromMilliseconds(250), TimeSpan.FromSeconds(1), token))
            {
                activeEndpoint = existingEndpoint;
                RevealStartupWindow();
                splash.SetStatus(afterUpdate ? FinishingUpdateStatus : "SoAI is already running...");
                return existingEndpoint;
            }

            splash.SetStatus("Requesting administrator access for the SoAI runtime...");
            ElevatedBackendSession session = await ElevatedBackendSession.StartAsync(paths, BuildStartArguments(originalArgs), token);
            try
            {
                backendSession = session;
                RevealStartupWindow();
                return await session.WaitForReadyAsync(splash, BackendStartupTimeout, token);
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

        private static string[] BuildStartArguments(string[] originalArgs)
        {
            List<string> args = new List<string>();
            bool hasNoBrowser = false;
            if (originalArgs != null)
            {
                foreach (string arg in originalArgs)
                {
                    if (string.Equals(arg, "-start-no-browser", StringComparison.OrdinalIgnoreCase)
                        || string.Equals(arg, "--start-no-browser", StringComparison.OrdinalIgnoreCase)
                        || string.Equals(arg, "start-no-browser", StringComparison.OrdinalIgnoreCase))
                    {
                        hasNoBrowser = true;
                    }
                    args.Add(arg);
                }
            }
            if (!hasNoBrowser)
            {
                args.Add("--start-no-browser");
            }
            return args.ToArray();
        }

        private async Task EnsureWebViewAsync()
        {
            string browserExecutableFolder = paths.ResolveWebView2RuntimeDirectory();
            EnsureWebViewRuntimeAvailable(browserExecutableFolder);
            string userDataFolder = Path.Combine(paths.StateDirectory, "launcher-webview2");
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
                TrustedWebContent.TryOpenExternalUri(uri, e.IsUserInitiated);
                return;
            }

            CoreWebView2Deferral deferral = e.GetDeferral();
            DetachedWebViewForm window = null;
            try
            {
                window = new DetachedWebViewForm(owner.Icon, lightTheme);
                RegisterDetachedWindow(window);
                await window.InitializeAsync(webViewEnvironment);
                await ConfigureWebViewAsync(window.WebView, window, false);
                e.NewWindow = window.WebView.CoreWebView2;
                if (TrustedWebContent.IsBlankWindowUri(uri))
                {
                    window.ShowHidden(owner);
                }
                else
                {
                    window.Show(owner);
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

        private async Task NavigateAndRevealAsync(EndpointInfo endpoint, CancellationToken token)
        {
            activeEndpoint = endpoint;
            splash.SetStatus("Opening SoAI...");
            frontendRevealed = new TaskCompletionSource<bool>();
            string bootHandoffScript = splash.UsesWebView
                ? await webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(splash.BuildBootHandoffScript())
                : null;
            try
            {
                TaskCompletionSource<bool> navigation = new TaskCompletionSource<bool>();
                EventHandler<CoreWebView2NavigationCompletedEventArgs> completed = null;
                completed = delegate(object sender, CoreWebView2NavigationCompletedEventArgs e)
                {
                    webView.CoreWebView2.NavigationCompleted -= completed;
                    if (e.IsSuccess)
                    {
                        navigation.TrySetResult(true);
                    }
                    else
                    {
                        navigation.TrySetException(new InvalidOperationException("The SoAI WebUI failed to load: " + e.WebErrorStatus.ToString()));
                    }
                };

                webView.CoreWebView2.NavigationCompleted += completed;
                webView.CoreWebView2.Navigate(endpoint.BaseUrl);

                await WaitForNavigationAsync(endpoint, navigation, token);
                await WaitForFrontendReadyAsync(token);
            }
            finally
            {
                if (bootHandoffScript != null)
                {
                    webView.CoreWebView2.RemoveScriptToExecuteOnDocumentCreated(bootHandoffScript);
                }
            }

            splash.BringToFront();
            await splash.ExitAsync(token);
            splash.Visible = false;
            ActiveControl = webView;
            webView.Select();
            webView.Focus();
        }

        private async Task WaitForNavigationAsync(EndpointInfo endpoint, TaskCompletionSource<bool> navigation, CancellationToken token)
        {
            DateTime deadline = DateTime.UtcNow.AddSeconds(45);
            DateTime unhealthySince = DateTime.MinValue;
            using (token.Register(delegate { navigation.TrySetCanceled(); }))
            {
                while (DateTime.UtcNow < deadline)
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
                        unhealthySince = DateTime.MinValue;
                    }
                    else if (unhealthySince == DateTime.MinValue)
                    {
                        unhealthySince = DateTime.UtcNow;
                    }
                    else if ((DateTime.UtcNow - unhealthySince) > TimeSpan.FromSeconds(5))
                    {
                        throw new InvalidOperationException("SoAI became unavailable while the app window was opening.");
                    }
                }
            }

            throw new TimeoutException("The SoAI WebUI did not finish opening within 45 seconds.");
        }

        private async Task WaitForFrontendReadyAsync(CancellationToken token)
        {
            Task revealed = frontendRevealed.Task;
            DateTime deadline = DateTime.UtcNow.AddSeconds(60);
            while (DateTime.UtcNow < deadline)
            {
                token.ThrowIfCancellationRequested();
                if (revealed.IsCompleted)
                {
                    return;
                }
                Task<string> scriptTask = webView.CoreWebView2.ExecuteScriptAsync(
                    "(function(){var d=document.documentElement;var p=document.getElementById('page-preloader');var login=document.querySelector('form,input[name=\"username\"],#username,[autocomplete=\"username\"]');return !!(document.readyState==='complete' && ((!d || !d.hasAttribute('data-soai-boot-state')) || login) && (!p || !p.isConnected || p.classList.contains('page-preloader--exiting') || login));})()");
                Task completed = await Task.WhenAny(scriptTask, revealed, Task.Delay(1000, token));
                if (completed == revealed)
                {
                    return;
                }
                if (completed != scriptTask)
                {
                    continue;
                }
                string result = await scriptTask;
                if (string.Equals(result, "true", StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
                await Task.WhenAny(revealed, Task.Delay(250, token));
            }

            throw new TimeoutException("The SoAI WebUI loaded, but the app did not become interactive within 60 seconds.");
        }

        private async void BeginUpdateHandoff(string targetVersion)
        {
            if (updateHandoffVersion != null || closeRequested)
            {
                return;
            }
            updateHandoffVersion = targetVersion;
            await MonitorUpdateHandoffAsync(activeEndpoint, targetVersion, shutdownToken.Token);
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
                next.Save(paths.StateDirectory);
            }
            lightTheme = light;
            LauncherAppearance.ApplyToWindow(this, light);
            webView.DefaultBackgroundColor = LauncherAppearance.BackgroundFor(light);
            splash.SetAppearance(light, next.InterfaceScale);
            foreach (DetachedWebViewForm window in detachedWindows)
            {
                window.ApplyTheme(light);
            }
        }

        private void OnFormClosing(object sender, FormClosingEventArgs e)
        {
            if (closeRequested)
            {
                return;
            }

            closeRequested = true;
            shutdownToken.Cancel();
            ReleaseBackend();
            CloseDetachedWindows();
        }

        private void CloseQuietly()
        {
            if (closeRequested)
            {
                return;
            }
            closeRequested = true;
            shutdownToken.Cancel();
            ReleaseBackend();
            CloseDetachedWindows();
            Close();
        }

        private void ReleaseBackend()
        {
            bool stopBackend = updateHandoffVersion == null;
            ElevatedBackendSession session = backendSession;
            backendSession = null;
            if (session != null)
            {
                try
                {
                    session.Release(stopBackend);
                }
                catch (Exception exception)
                {
                    LauncherDiagnostics.WriteStartupFailure(paths, exception);
                }
                return;
            }

            EndpointInfo endpoint = activeEndpoint;
            activeEndpoint = null;
            if (endpoint == null || !stopBackend)
            {
                return;
            }

            try
            {
                BackendProcess.StartDetached(paths, new string[] { "--stop" });
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
            }
        }

        private void RegisterDetachedWindow(DetachedWebViewForm window)
        {
            detachedWindows.Add(window);
            window.FormClosed += delegate
            {
                detachedWindows.Remove(window);
            };
        }

        private void CloseDetachedWindows()
        {
            DetachedWebViewForm[] windows = detachedWindows.ToArray();
            detachedWindows.Clear();
            foreach (DetachedWebViewForm window in windows)
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
            if (resolvedOpacity >= 0.999f)
            {
                g.DrawImage(image, Rectangle.Round(rect), 0, 0, image.Width, image.Height, GraphicsUnit.Pixel);
                return;
            }
            using (System.Drawing.Imaging.ImageAttributes attributes = new System.Drawing.Imaging.ImageAttributes())
            {
                System.Drawing.Imaging.ColorMatrix matrix = new System.Drawing.Imaging.ColorMatrix();
                matrix.Matrix33 = resolvedOpacity;
                attributes.SetColorMatrix(matrix, System.Drawing.Imaging.ColorMatrixFlag.Default, System.Drawing.Imaging.ColorAdjustType.Bitmap);
                g.DrawImage(image, Rectangle.Round(rect), 0, 0, image.Width, image.Height, GraphicsUnit.Pixel, attributes);
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
        private const int TrailSegmentCount = 64;
        private Bitmap image;
        private int imageSize;
        private float imageRing;
        private int imageTrackColor;
        private int imageActiveColor;

        public Image Resolve(float size, float ring, SplashPalette palette)
        {
            int resolvedSize = Math.Max(1, (int)Math.Ceiling(size));
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
            using (Graphics graphics = Graphics.FromImage(rendered))
            {
                graphics.SmoothingMode = SmoothingMode.AntiAlias;
                graphics.PixelOffsetMode = PixelOffsetMode.HighQuality;
                graphics.Clear(Color.Transparent);
                RectangleF bounds = new RectangleF(0.0f, 0.0f, size, size);
                RectangleF ringBounds = RectangleF.Inflate(bounds, -ring / 2.0f, -ring / 2.0f);
                using (Pen trackPen = new Pen(trackColor, ring))
                {
                    graphics.DrawEllipse(trackPen, ringBounds);
                }
                float trailSweep = 360.0f - TrailStartDegrees;
                float segmentSweep = trailSweep / TrailSegmentCount;
                using (Pen trailPen = new Pen(Color.Transparent, ring))
                {
                    trailPen.StartCap = LineCap.Flat;
                    trailPen.EndCap = LineCap.Flat;
                    for (int segmentIndex = 0; segmentIndex < TrailSegmentCount; segmentIndex++)
                    {
                        float progress = (segmentIndex + 1.0f) / TrailSegmentCount;
                        int alpha = Math.Max(1, (int)Math.Round(activeColor.A * progress * progress));
                        trailPen.Color = Color.FromArgb(alpha, activeColor);
                        float startAngle = -90.0f + TrailStartDegrees + (segmentSweep * segmentIndex);
                        graphics.DrawArc(trailPen, ringBounds, startAngle, segmentSweep + 0.75f);
                    }
                }
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
                var align = function (elements, origin) {
                    var elapsed = Math.max(0, Date.now() - origin);
                    elements.forEach(function (element) {
                        element.getAnimations().forEach(function (animation) {
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
                    align([spinner], startedAt);
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
        public const string HostDirectoryName = "update-progress";
        private const string Argument = "--soai-update-progress";

        public static bool IsCommand(string[] args)
        {
            return args != null && args.Length == 3 && string.Equals(args[0], Argument, StringComparison.Ordinal);
        }

        public static int Run(string[] args)
        {
            string installRoot = Path.GetFullPath(args[1]);
            if (!File.Exists(Path.Combine(installRoot, ".soai-install-root")) || !ReleaseVersionText.IsValid(args[2]))
            {
                return 2;
            }
            if (PrivilegeState.IsElevated())
            {
                try
                {
                    UnelevatedLauncher.StartFromDesktopShell(AppDomain.CurrentDomain.BaseDirectory, args);
                    return 0;
                }
                catch (Win32Exception)
                {
                }
                catch (InvalidOperationException)
                {
                }
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (UpdateProgressForm form = new UpdateProgressForm(installRoot, args[2]))
            {
                Application.Run(form);
            }
            return 0;
        }

        public static void RemoveRetainedHost(LauncherPaths paths)
        {
            string host = Path.Combine(paths.StateDirectory, HostDirectoryName);
            try
            {
                if (Directory.Exists(host))
                {
                    Directory.Delete(host, true);
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }

    internal sealed class UpdateProgressForm : Form
    {
        private static readonly TimeSpan MaximumLifetime = TimeSpan.FromHours(3);
        private static readonly TimeSpan SettledGracePeriod = TimeSpan.FromMinutes(2);
        private const string ReopenNotice = "SoAI will reopen automatically when it is ready.";
        private const string DurationNotice = "This can take several minutes. Don't turn off your computer.";

        private readonly string installRoot;
        private readonly string launcherPath;
        private readonly string targetVersion;
        private readonly SplashView splash;
        private readonly System.Windows.Forms.Timer poll;
        private readonly DateTime deadlineUtc;
        private DateTime? settledSinceUtc;

        public UpdateProgressForm(string installRoot, string targetVersion)
        {
            this.installRoot = installRoot;
            this.launcherPath = Path.Combine(installRoot, "soai.exe");
            this.targetVersion = targetVersion;
            this.deadlineUtc = DateTime.UtcNow + MaximumLifetime;
            LauncherPaths assets = LauncherPaths.ForAssetDirectory(AppDomain.CurrentDomain.BaseDirectory);
            LauncherAppearance appearance = LauncherAppearance.Load(Path.Combine(installRoot, "data", "state"));
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
            poll.Tick += delegate { RefreshProgress(); };
            Shown += delegate
            {
                splash.Reveal();
                poll.Start();
            };
        }

        private void RefreshProgress()
        {
            DateTime now = DateTime.UtcNow;
            bool pending = TransactionIsPending();
            settledSinceUtc = pending ? (DateTime?)null : (settledSinceUtc ?? now);
            bool settled = settledSinceUtc.HasValue && now - settledSinceUtc.Value >= SettledGracePeriod;
            if (now >= deadlineUtc || settled || LauncherWindowIsVisible())
            {
                poll.Stop();
                Close();
                return;
            }
            splash.SetStatus(DescribeProgress(pending));
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
            StartPosition = FormStartPosition.CenterParent;
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

        public void ShowHidden(IWin32Window owner)
        {
            hiddenUntilContent = true;
            Opacity = 0.0;
            ShowInTaskbar = false;
            Show(owner);
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

        public static async Task AttachAsync(
            CoreWebView2 core,
            Func<string, bool> isTrustedSource,
            Action<string> onUpdateHandoff,
            Action onBootReveal,
            Action<LauncherAppearance, bool> onAppearance)
        {
            await core.AddScriptToExecuteOnDocumentCreatedAsync(
                "(function(){'use strict';var capability=Object.freeze({platform:'windows',protocolVersion:1});" +
                "try{Object.defineProperty(window,'soaiDesktopLauncher',{value:capability,writable:false,configurable:false});}" +
                "catch(e){window.soaiDesktopLauncher=capability;}})();");
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
        private const uint TOKEN_QUERY = 0x00000008;
        private const uint CREATE_SUSPENDED = 0x00000004;
        private const uint EXTENDED_STARTUPINFO_PRESENT = 0x00080000;
        private const int TOKEN_ELEVATION_CLASS = 20;
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

        public static bool TryLaunch(LauncherPaths paths, string[] args)
        {
            try
            {
                List<string> forwarded = new List<string>(CompleteHandoff(args));
                forwarded.Add(HandoffArgument);
                StartFromDesktopShell(paths.RootDirectory, forwarded.ToArray());
                return true;
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                MessageBox.Show("SoAI could not start in the standard desktop session. Start SoAI from its desktop shortcut.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return false;
            }
        }

        public static void StartFromDesktopShell(string workingDirectory, string[] args)
        {
            IntPtr shellWindow = GetShellWindow();
            if (shellWindow == IntPtr.Zero)
            {
                throw new InvalidOperationException("The Windows desktop shell is not available.");
            }
            int shellProcessId;
            GetWindowThreadProcessId(shellWindow, out shellProcessId);
            if (shellProcessId <= 0)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to identify the Windows desktop shell.");
            }
            IntPtr shellProcess = OpenProcess(PROCESS_CREATE_PROCESS, false, shellProcessId);
            if (shellProcess == IntPtr.Zero)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to open the Windows desktop shell.");
            }
            IntPtr attributeList = IntPtr.Zero;
            IntPtr parentProcessValue = IntPtr.Zero;
            PROCESS_INFORMATION processInformation = new PROCESS_INFORMATION();
            bool attributeListInitialized = false;
            bool processResumed = false;
            try
            {
                IntPtr attributeListSize = IntPtr.Zero;
                InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref attributeListSize);
                if (attributeListSize == IntPtr.Zero)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to size the desktop process attributes.");
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
                string executable = Application.ExecutablePath;
                StringBuilder commandLine = new StringBuilder(BackendProcess.Quote(executable) + BackendProcess.BuildArgumentString(args));
                if (!CreateProcess(executable, commandLine, IntPtr.Zero, IntPtr.Zero, false, CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT, IntPtr.Zero, workingDirectory, ref startupInformation, out processInformation))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to start SoAI from the Windows desktop shell.");
                }
                RequireStandardToken(processInformation.hProcess);
                if (ResumeThread(processInformation.hThread) == UInt32.MaxValue)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to resume SoAI in the standard desktop session.");
                }
                processResumed = true;
            }
            finally
            {
                if (processInformation.hProcess != IntPtr.Zero && !processResumed)
                {
                    TerminateProcess(processInformation.hProcess, 1);
                }
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
                CloseHandle(shellProcess);
            }
        }

        private static void RequireStandardToken(IntPtr process)
        {
            IntPtr token = IntPtr.Zero;
            try
            {
                if (!OpenProcessToken(process, TOKEN_QUERY, out token))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to inspect the desktop launcher token.");
                }
                TOKEN_ELEVATION elevation;
                int returnedLength;
                if (!GetTokenInformation(token, TOKEN_ELEVATION_CLASS, out elevation, Marshal.SizeOf(typeof(TOKEN_ELEVATION)), out returnedLength))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to read the desktop launcher elevation state.");
                }
                if (elevation.TokenIsElevated != 0)
                {
                    throw new InvalidOperationException("The Windows desktop shell did not provide a standard-user process token.");
                }
            }
            finally
            {
                if (token != IntPtr.Zero)
                {
                    CloseHandle(token);
                }
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
        private struct TOKEN_ELEVATION
        {
            public int TokenIsElevated;
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
        private static extern bool GetTokenInformation(IntPtr tokenHandle, int tokenInformationClass, out TOKEN_ELEVATION tokenInformation, int tokenInformationLength, out int returnLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool InitializeProcThreadAttributeList(IntPtr attributeList, int attributeCount, int flags, ref IntPtr size);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool UpdateProcThreadAttribute(IntPtr attributeList, uint flags, IntPtr attribute, IntPtr value, IntPtr size, IntPtr previousValue, IntPtr returnSize);

        [DllImport("kernel32.dll")]
        private static extern void DeleteProcThreadAttributeList(IntPtr attributeList);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateProcess(string applicationName, StringBuilder commandLine, IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles, uint creationFlags, IntPtr environment, string currentDirectory, ref STARTUPINFOEX startupInformation, out PROCESS_INFORMATION processInformation);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint ResumeThread(IntPtr thread);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateProcess(IntPtr process, uint exitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);
    }

    internal sealed class ElevatedBackendSession : IDisposable
    {
        private const string HelperArgument = "--soai-elevated-backend-helper";
        private static readonly TimeSpan HelperShutdownTimeout = TimeSpan.FromSeconds(150);
        private readonly NamedPipeServerStream pipe;
        private readonly StreamReader reader;
        private readonly StreamWriter writer;
        private readonly Process helperProcess;
        private bool ready;
        private bool stopRequested;

        private ElevatedBackendSession(NamedPipeServerStream pipe, StreamReader reader, StreamWriter writer, Process helperProcess)
        {
            this.pipe = pipe;
            this.reader = reader;
            this.writer = writer;
            this.helperProcess = helperProcess;
        }

        private static PipeSecurity BuildCurrentUserOnlyPipeSecurity()
        {
            PipeSecurity security = new PipeSecurity();
            security.SetAccessRuleProtection(true, false);
            SecurityIdentifier currentUser = WindowsIdentity.GetCurrent().User;
            security.AddAccessRule(new PipeAccessRule(currentUser, PipeAccessRights.FullControl, AccessControlType.Allow));
            return security;
        }

        public static async Task<ElevatedBackendSession> StartAsync(LauncherPaths paths, string[] backendArgs, CancellationToken token)
        {
            string parentEnvironment = CaptureParentEnvironment();
            string pipeName = "SoAI-Backend-" + Guid.NewGuid().ToString("N");
            string authenticationToken = Convert.ToBase64String(Guid.NewGuid().ToByteArray()) + Convert.ToBase64String(Guid.NewGuid().ToByteArray());
            NamedPipeServerStream pipe = new NamedPipeServerStream(
                pipeName,
                PipeDirection.InOut,
                1,
                PipeTransmissionMode.Message,
                PipeOptions.Asynchronous,
                0,
                0,
                BuildCurrentUserOnlyPipeSecurity());
            Process helper = null;
            try
            {
                ProcessStartInfo startInfo = new ProcessStartInfo();
                startInfo.FileName = NativeBackendJob.ResolveProcessPath(Application.ExecutablePath);
                startInfo.Arguments = BackendProcess.Quote(HelperArgument)
                    + " " + BackendProcess.Quote(pipeName)
                    + " " + BackendProcess.Quote(authenticationToken)
                    + BackendProcess.BuildArgumentString(backendArgs);
                startInfo.WorkingDirectory = NativeBackendJob.ResolveProcessPath(paths.RootDirectory, true);
                startInfo.UseShellExecute = true;
                startInfo.Verb = "runas";
                startInfo.WindowStyle = ProcessWindowStyle.Hidden;
                try
                {
                    helper = Process.Start(startInfo);
                }
                catch (Win32Exception exception)
                {
                    if (exception.NativeErrorCode == 1223)
                    {
                        throw new OperationCanceledException("Administrator access was cancelled.", exception, token);
                    }
                    throw;
                }
                Task connection = pipe.WaitForConnectionAsync(token);
                Task connectionCompleted = await Task.WhenAny(connection, Task.Delay(TimeSpan.FromSeconds(30), token));
                if (connectionCompleted != connection)
                {
                    token.ThrowIfCancellationRequested();
                    throw new TimeoutException("The administrator runtime helper did not connect within 30 seconds.");
                }
                await connection;
                StreamReader reader = new StreamReader(pipe, Encoding.UTF8, false, 1024, true);
                StreamWriter writer = new StreamWriter(pipe, new UTF8Encoding(false), 1024, true);
                writer.AutoFlush = true;
                Task<string> greetingRead = reader.ReadLineAsync();
                Task greetingCompleted = await Task.WhenAny(greetingRead, Task.Delay(TimeSpan.FromSeconds(10), token));
                if (greetingCompleted != greetingRead)
                {
                    token.ThrowIfCancellationRequested();
                    throw new TimeoutException("The administrator runtime helper did not authenticate within 10 seconds.");
                }
                string greeting = await greetingRead;
                if (!string.Equals(greeting, "HELLO\t" + authenticationToken, StringComparison.Ordinal))
                {
                    throw new InvalidOperationException("The elevated SoAI runtime helper failed authentication.");
                }
                Task environmentWrite = writer.WriteLineAsync(parentEnvironment);
                Task environmentWritten = await Task.WhenAny(environmentWrite, Task.Delay(TimeSpan.FromSeconds(10), token));
                if (environmentWritten != environmentWrite)
                {
                    token.ThrowIfCancellationRequested();
                    throw new TimeoutException("The administrator runtime environment could not be transferred within 10 seconds.");
                }
                await environmentWrite;
                Task<string> environmentRead = reader.ReadLineAsync();
                Task environmentCompleted = await Task.WhenAny(environmentRead, Task.Delay(TimeSpan.FromSeconds(10), token));
                if (environmentCompleted != environmentRead)
                {
                    token.ThrowIfCancellationRequested();
                    throw new TimeoutException("The administrator runtime helper did not acknowledge its environment within 10 seconds.");
                }
                if (!string.Equals(await environmentRead, "ENVIRONMENT_ACCEPTED", StringComparison.Ordinal))
                {
                    throw new InvalidOperationException("The administrator runtime helper rejected its environment.");
                }
                return new ElevatedBackendSession(pipe, reader, writer, helper);
            }
            catch
            {
                pipe.Dispose();
                if (helper != null)
                {
                    BackendProcess.KillQuietly(helper);
                }
                throw;
            }
        }

        private static string CaptureParentEnvironment()
        {
            List<string[]> environment = new List<string[]>();
            System.Collections.IDictionary snapshot = Environment.GetEnvironmentVariables();
            foreach (string name in snapshot.Keys)
            {
                if (snapshot[name] == null)
                {
                    throw new InvalidOperationException("The launcher environment snapshot contains an invalid value.");
                }
                environment.Add(new string[] { name, snapshot[name].ToString() });
            }
            using (MemoryStream payload = new MemoryStream())
            using (BinaryWriter writer = new BinaryWriter(payload, new UTF8Encoding(false, true)))
            {
                writer.Write(environment.Count);
                foreach (string[] entry in environment)
                {
                    writer.Write(entry[0]);
                    writer.Write(entry[1]);
                }
                writer.Flush();
                return "ENVIRONMENT\t" + Convert.ToBase64String(payload.ToArray());
            }
        }

        public async Task<EndpointInfo> WaitForReadyAsync(SplashView splash, TimeSpan timeout, CancellationToken token)
        {
            DateTime deadline = DateTime.UtcNow.Add(timeout);
            Task<string> pendingRead = reader.ReadLineAsync();
            try
            {
                while (DateTime.UtcNow < deadline)
                {
                    token.ThrowIfCancellationRequested();
                    Task completed = await Task.WhenAny(pendingRead, Task.Delay(500, token));
                    if (completed == pendingRead)
                    {
                        string message = await pendingRead;
                        if (message == null)
                        {
                            throw new InvalidOperationException("The elevated SoAI runtime helper disconnected before readiness.");
                        }
                        if (message.StartsWith("STATUS\t", StringComparison.Ordinal))
                        {
                            splash.SetStatus(message.Substring(7));
                        }
                        else if (string.Equals(message, "READY", StringComparison.Ordinal))
                        {
                            EndpointInfo endpoint = await DiscoveryProbe.WaitForEndpointAsync(TimeSpan.FromMilliseconds(250), TimeSpan.FromSeconds(10), token);
                            if (endpoint == null || !await HealthProbe.WaitForReadyAsync(endpoint, TimeSpan.FromMilliseconds(250), TimeSpan.FromSeconds(10), token))
                            {
                                throw new InvalidOperationException("The elevated backend reported readiness without a healthy endpoint.");
                            }
                            writer.WriteLine("COMMIT");
                            Task<string> commitRead = reader.ReadLineAsync();
                            Task commitCompleted = await Task.WhenAny(commitRead, Task.Delay(TimeSpan.FromSeconds(10), token));
                            if (commitCompleted != commitRead)
                            {
                                token.ThrowIfCancellationRequested();
                                throw new TimeoutException("The elevated backend did not confirm startup ownership transfer.");
                            }
                            string commitMessage = await commitRead;
                            if (!string.Equals(commitMessage, "COMMITTED", StringComparison.Ordinal))
                            {
                                throw new InvalidOperationException("The elevated backend did not complete startup ownership transfer.");
                            }
                            ready = true;
                            splash.SetStatus("SoAI is ready...");
                            return endpoint;
                        }
                        else if (message.StartsWith("ERROR\t", StringComparison.Ordinal))
                        {
                            throw new InvalidOperationException(message.Substring(6));
                        }
                        pendingRead = reader.ReadLineAsync();
                    }
                    if (helperProcess.HasExited && !ready)
                    {
                        throw new InvalidOperationException("The elevated SoAI runtime helper exited before readiness.");
                    }
                }
                throw new TimeoutException("SoAI did not become ready within " + ((int)timeout.TotalMinutes).ToString(CultureInfo.InvariantCulture) + " minutes.");
            }
            catch
            {
                TryCancel();
                throw;
            }
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
            catch
            {
            }
        }

        public void RequestStop()
        {
            RequestRelease(true);
        }

        private void RequestRelease(bool stopBackend)
        {
            if (stopRequested)
            {
                return;
            }
            stopRequested = true;
            if (ready && pipe.IsConnected)
            {
                writer.WriteLine(stopBackend ? "STOP" : "RELEASE");
            }
            else
            {
                TryCancel();
            }
        }

        public void Release(bool stopBackend)
        {
            try
            {
                RequestRelease(stopBackend);
            }
            finally
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
                        try
                        {
                            pipe.Dispose();
                        }
                        finally
                        {
                            helperProcess.Dispose();
                        }
                    }
                }
            }
        }

        public void Dispose()
        {
            try
            {
                if (ready)
                {
                    RequestStop();
                }
                else
                {
                    TryCancel();
                }
                if (!helperProcess.HasExited && !helperProcess.WaitForExit((int)HelperShutdownTimeout.TotalMilliseconds))
                {
                    throw new TimeoutException("The elevated SoAI runtime helper did not finish shutdown within 150 seconds.");
                }
            }
            finally
            {
                try
                {
                    writer.Dispose();
                }
                catch (IOException)
                {
                    if (pipe.IsConnected)
                    {
                        throw;
                    }
                }
                finally
                {
                    try
                    {
                        reader.Dispose();
                    }
                    finally
                    {
                        try
                        {
                            pipe.Dispose();
                        }
                        finally
                        {
                            helperProcess.Dispose();
                        }
                    }
                }
            }
        }
    }

    internal static class ElevatedBackendHelper
    {
        private const string HelperArgument = "--soai-elevated-backend-helper";
        private static readonly TimeSpan ReleasedBackendExitTimeout = TimeSpan.FromMinutes(5);

        public static bool IsHelperCommand(string[] args)
        {
            return args != null && args.Length >= 3 && string.Equals(args[0], HelperArgument, StringComparison.Ordinal);
        }

        public static int Run(LauncherPaths paths, string[] args)
        {
            if (!PrivilegeState.IsElevated() || args == null || args.Length < 3)
            {
                return 1;
            }
            string pipeName = args[1] ?? string.Empty;
            string authenticationToken = args[2] ?? string.Empty;
            if (pipeName.Length < 16 || authenticationToken.Length < 32)
            {
                return 1;
            }
            string[] backendArgs = new string[args.Length - 3];
            Array.Copy(args, 3, backendArgs, 0, backendArgs.Length);
            UpdateProgressWindow.RemoveRetainedHost(paths);
            try
            {
                using (NamedPipeClientStream pipe = new NamedPipeClientStream(".", pipeName, PipeDirection.InOut, PipeOptions.Asynchronous, TokenImpersonationLevel.Identification))
                {
                    pipe.Connect(15000);
                    using (StreamReader reader = new StreamReader(pipe, Encoding.UTF8, false, 1024, true))
                    using (StreamWriter writer = new StreamWriter(pipe, new UTF8Encoding(false), 1024, true))
                    {
                        writer.AutoFlush = true;
                        writer.WriteLine("HELLO\t" + authenticationToken);
                        ReceiveParentEnvironment(reader, writer);
                        return RunOwnedBackend(paths, backendArgs, pipe, reader, writer);
                    }
                }
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                return 1;
            }
        }

        internal static void ReceiveParentEnvironment(StreamReader reader, StreamWriter writer)
        {
            Task<string> environmentRead = reader.ReadLineAsync();
            if (!environmentRead.Wait(TimeSpan.FromSeconds(10)))
            {
                throw new TimeoutException("The launcher did not supply the administrator runtime environment within 10 seconds.");
            }
            string message = environmentRead.GetAwaiter().GetResult();
            const string prefix = "ENVIRONMENT\t";
            if (message == null || !message.StartsWith(prefix, StringComparison.Ordinal))
            {
                throw new InvalidOperationException("The launcher environment transfer is missing or invalid.");
            }
            Dictionary<string, string> environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            try
            {
                using (MemoryStream payload = new MemoryStream(Convert.FromBase64String(message.Substring(prefix.Length))))
                using (BinaryReader decoder = new BinaryReader(payload, new UTF8Encoding(false, true)))
                {
                    int count = decoder.ReadInt32();
                    if (count < 0 || count > payload.Length / 2)
                    {
                        throw new InvalidOperationException("The launcher environment entry count is invalid.");
                    }
                    for (int index = 0; index < count; index++)
                    {
                        string name = decoder.ReadString();
                        string value = decoder.ReadString();
                        if (string.IsNullOrEmpty(name) || name.IndexOf('=') >= 0 || name.IndexOf('\0') >= 0
                            || value.IndexOf('\0') >= 0 || environment.ContainsKey(name))
                        {
                            throw new InvalidOperationException("The launcher environment contains invalid or duplicate entries.");
                        }
                        environment.Add(name, value);
                    }
                    if (payload.Position != payload.Length)
                    {
                        throw new InvalidOperationException("The launcher environment contains trailing data.");
                    }
                }
            }
            catch (ArgumentException)
            {
                throw new InvalidOperationException("The launcher environment transfer is malformed.");
            }
            catch (FormatException)
            {
                throw new InvalidOperationException("The launcher environment transfer is malformed.");
            }
            catch (IOException)
            {
                throw new InvalidOperationException("The launcher environment transfer is truncated or unreadable.");
            }
            foreach (string name in Environment.GetEnvironmentVariables().Keys)
            {
                if (!SetProcessEnvironmentVariable(name, null))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "The administrator runtime environment could not be cleared.");
                }
            }
            foreach (KeyValuePair<string, string> entry in environment)
            {
                if (!SetProcessEnvironmentVariable(entry.Key, entry.Value))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "The administrator runtime environment could not be restored.");
                }
            }
            writer.WriteLine("ENVIRONMENT_ACCEPTED");
        }

        [DllImport("kernel32.dll", EntryPoint = "SetEnvironmentVariableW", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetProcessEnvironmentVariable(string name, string value);

        private static int RunOwnedBackend(LauncherPaths paths, string[] backendArgs, NamedPipeClientStream pipe, StreamReader reader, StreamWriter writer)
        {
            string mutexName = "Global\\SoAI-Backend-" + StableRootIdentity(paths.RootDirectory);
            using (Mutex startupMutex = new Mutex(false, mutexName))
            {
                bool acquired = false;
                Task<string> cancellationRead = reader.ReadLineAsync();
                try
                {
                    DateTime deadline = DateTime.UtcNow.AddMinutes(20);
                    while (!acquired && DateTime.UtcNow < deadline)
                    {
                        if (IsCancellationRequested(cancellationRead))
                        {
                            return 0;
                        }
                        try
                        {
                            acquired = startupMutex.WaitOne(TimeSpan.FromMilliseconds(250));
                        }
                        catch (AbandonedMutexException)
                        {
                            acquired = true;
                        }
                    }
                    if (!acquired)
                    {
                        writer.WriteLine("ERROR\tTimed out waiting for another SoAI startup attempt.");
                        return 1;
                    }
                    if (IsCancellationRequested(cancellationRead))
                    {
                        return 0;
                    }
                    return RunBackendAfterMutexAsync(paths, backendArgs, cancellationRead, reader, writer).GetAwaiter().GetResult();
                }
                catch (IOException)
                {
                    return 1;
                }
                catch (Exception exception)
                {
                    LauncherDiagnostics.WriteStartupFailure(paths, exception);
                    try
                    {
                        if (pipe.IsConnected)
                        {
                            writer.WriteLine("ERROR\tThe administrator backend failed to start. See the SoAI startup log for details.");
                        }
                    }
                    catch
                    {
                    }
                    return 1;
                }
                finally
                {
                    if (acquired)
                    {
                        startupMutex.ReleaseMutex();
                    }
                }
            }
        }

        private static async Task<int> RunBackendAfterMutexAsync(LauncherPaths paths, string[] backendArgs, Task<string> cancellationRead, StreamReader reader, StreamWriter writer)
        {
            EndpointInfo existing = await DiscoveryProbe.WaitForEndpointAsync(TimeSpan.FromMilliseconds(250), TimeSpan.FromSeconds(2), CancellationToken.None);
            if (existing != null && await HealthProbe.WaitForReadyAsync(existing, TimeSpan.FromMilliseconds(250), TimeSpan.FromSeconds(2), CancellationToken.None))
            {
                writer.WriteLine("READY");
                string decision = await cancellationRead;
                if (!string.Equals(decision, "COMMIT", StringComparison.Ordinal))
                {
                    return 0;
                }
                await CompleteOwnershipTransferAsync(paths, reader, writer, null);
                return 0;
            }
            writer.WriteLine("STATUS\tLaunching the administrator backend...");
            using (NativeBackendJob backend = NativeBackendJob.Start(paths, backendArgs))
            {
                DateTime deadline = DateTime.UtcNow.AddMinutes(20);
                while (DateTime.UtcNow < deadline)
                {
                    if (IsCancellationRequested(cancellationRead))
                    {
                        return 0;
                    }
                    if (backend.HasExited)
                    {
                        int exitCode = backend.ExitCode;
                        LauncherDiagnostics.WriteBackendExitFailure(paths, exitCode);
                        writer.WriteLine("ERROR\tSoAI stopped before it became ready with backend exit code " + exitCode.ToString(CultureInfo.InvariantCulture) + ". Recent backend output was added to the startup diagnostic.");
                        return 1;
                    }
                    EndpointInfo endpoint = await DiscoveryProbe.TryResolveAsync(CancellationToken.None);
                    if (endpoint != null && await HealthProbe.IsReadyAsync(endpoint, CancellationToken.None))
                    {
                        writer.WriteLine("READY");
                        string decision = await cancellationRead;
                        if (!string.Equals(decision, "COMMIT", StringComparison.Ordinal))
                        {
                            return 0;
                        }
                        await CompleteOwnershipTransferAsync(paths, reader, writer, backend);
                        return 0;
                    }
                    writer.WriteLine("STATUS\tWaiting for SoAI to become ready...");
                    await Task.Delay(500);
                }
                writer.WriteLine("ERROR\tSoAI backend startup timed out.");
                return 1;
            }
        }

        private static async Task CompleteOwnershipTransferAsync(LauncherPaths paths, StreamReader reader, StreamWriter writer, NativeBackendJob ownedBackend)
        {
            writer.WriteLine("COMMITTED");
            string trailingMessage = await reader.ReadLineAsync();
            if (string.Equals(trailingMessage, "RELEASE", StringComparison.Ordinal))
            {
                if (ownedBackend != null && !ownedBackend.ProcessHandle.WaitForExit((int)ReleasedBackendExitTimeout.TotalMilliseconds))
                {
                    throw new TimeoutException("The administrator backend did not finish its update shutdown after the launcher released it.");
                }
                return;
            }
            if (trailingMessage != null && !string.Equals(trailingMessage, "STOP", StringComparison.Ordinal))
            {
                throw new InvalidOperationException("The launcher sent data after completing startup ownership transfer.");
            }
            int exitCode = BackendProcess.RunForeground(paths, new string[] { "--stop" });
            if (exitCode != 0)
            {
                throw new InvalidOperationException("The administrator backend did not stop cleanly after the launcher closed.");
            }
        }

        private static bool IsCancellationRequested(Task<string> cancellationRead)
        {
            if (!cancellationRead.IsCompleted)
            {
                return false;
            }
            string message = cancellationRead.GetAwaiter().GetResult();
            return message == null || string.Equals(message, "CANCEL", StringComparison.Ordinal);
        }

        private static string StableRootIdentity(string rootDirectory)
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
    }

    public static class NativeFilesystemHandles
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern SafeFileHandle CreateFile(string fileName, uint desiredAccess, uint shareMode, IntPtr securityAttributes, uint creationDisposition, uint flagsAndAttributes, IntPtr templateFile);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern bool CreateDirectory(string path, IntPtr securityAttributes);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern uint GetFileAttributes(string path);

        [StructLayout(LayoutKind.Sequential)]
        private struct LockFileInformation
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
        private static extern bool GetFileInformationByHandle(SafeFileHandle handle, out LockFileInformation information);

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
                LockFileInformation identity;
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
            LockFileInformation information;
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

    public sealed class NativeBackendJob : IDisposable
    {
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

        internal static NativeBackendJob Start(LauncherPaths paths, string[] args)
        {
            string python = ResolveProcessPath(BackendProcess.ResolvePython(paths, args), preserveExecutableNamespace: true);
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
            string logical = path.StartsWith("\\\\?\\UNC\\", StringComparison.OrdinalIgnoreCase)
                ? "\\\\" + path.Substring(8)
                : path.StartsWith("\\\\?\\", StringComparison.Ordinal) ? path.Substring(4) : path;
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
            if (result.StartsWith("\\\\?\\UNC\\", StringComparison.OrdinalIgnoreCase)) { result = "\\\\" + result.Substring(8); }
            else if (result.StartsWith("\\\\?\\", StringComparison.Ordinal)) { result = result.Substring(4); }
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
                    if (!TerminateProcess(processInfo.hProcess, 1) && WaitForSingleObject(processInfo.hProcess, 0) != 0)
                    {
                        throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to stop the incomplete backend startup.");
                    }
                    if (WaitForSingleObject(processInfo.hProcess, 10000) != 0)
                    {
                        throw new TimeoutException("The incomplete backend startup did not exit; recovery requires repair.");
                    }
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
                JOBOBJECT_BASIC_ACCOUNTING_INFORMATION information;
                if (!QueryInformationJobObject(job, JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION, out information, Marshal.SizeOf(typeof(JOBOBJECT_BASIC_ACCOUNTING_INFORMATION)), IntPtr.Zero))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to verify backend job exit; recovery requires repair.");
                }
                if (information.ActiveProcesses == 0)
                {
                    return;
                }
                Thread.Sleep(25);
            }
            while (deadline.Elapsed < TimeSpan.FromSeconds(10));
            throw new TimeoutException("Backend descendants remain active; recovery requires repair.");
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
            Mutex bootstrapGate = null;
            try
            {
                RetainInstallPath(stagingParent, retainedHandles);
                RetainInstallPath(paths.RootDirectory, retainedHandles);
                string scriptSource = Path.Combine(paths.RootDirectory, "installer-support", "Install-SoAIRuntime.ps1");
                string metadataSource = Path.Combine(paths.RootDirectory, "installer-support", "dependencies-v1.json");
                RetainInstallPath(scriptSource, retainedHandles);
                RetainInstallPath(metadataSource, retainedHandles);
                operationDirectory = CreateInstallOperationDirectory(stagingParent);
                File.WriteAllText(Path.Combine(operationDirectory, "install-root.txt"), paths.RootDirectory, Encoding.UTF8);
                string script = Path.Combine(operationDirectory, "Install-SoAIRuntime.ps1");
                File.Copy(LauncherPaths.ToNativeFilesystemPath(scriptSource), LauncherPaths.ToNativeFilesystemPath(script), false);
                File.Copy(LauncherPaths.ToNativeFilesystemPath(metadataSource), LauncherPaths.ToNativeFilesystemPath(Path.Combine(operationDirectory, "dependencies-v1.json")), false);
                bool missingPython = !File.Exists(LauncherPaths.ToNativeFilesystemPath(paths.ResolveStandalonePythonExecutable()));
                string preflightArguments = "-PreflightOnly";
                if (missingPython)
                {
                    string identityPath = Path.Combine(paths.RootDirectory, "release-info-v1.json");
                    RetainInstallPath(identityPath, retainedHandles);
                    RetainInstallPath(Path.Combine(paths.RootDirectory, "VERSION"), retainedHandles);
                    RetainInstallPath(paths.BackendMain, retainedHandles);
                    bootstrapGate = OpenSourceBootstrapGate(paths);
                    preflightArguments += " -InstallRoot " + Quote(paths.RootDirectory);
                }
                int result = RunInstallPreparation(powershell, script, operationDirectory, preflightArguments, "preflight.log");
                if (result != 0)
                {
                    return result;
                }
                if (missingPython)
                {
                    result = RunInstallPreparation(
                        powershell, script, operationDirectory,
                        "-BootstrapOnly -InstallRoot " + Quote(paths.RootDirectory)
                            + " -DiagnosticRoot " + Quote(Path.Combine(operationDirectory, "runtime")), "bootstrap.log");
                    if (result != 0)
                    {
                        return result;
                    }
                }
                succeeded = true;
                return 0;
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
                if (bootstrapGate != null) { bootstrapGate.Dispose(); }
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

        private static Mutex OpenSourceBootstrapGate(LauncherPaths paths)
        {
            string lockPath = Environment.GetEnvironmentVariable("SOAI_INSTALL_LOCK_HELD_PATH");
            if (!string.IsNullOrEmpty(lockPath))
            {
                string expectedPath = Path.Combine(paths.RootDirectory, "data", "state", "locks", "soai.install.lock.d");
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
                INSTALL_PROCESS_IDENTITY identity;
                int returnedLength;
                int queryStatus = QueryInstallProcessIdentity(new IntPtr(-1), 0, out identity, Marshal.SizeOf(typeof(INSTALL_PROCESS_IDENTITY)), out returnedLength);
                using (Process owner = Process.GetProcessById(ownerPid))
                {
                    double ownerSeconds = owner.StartTime.ToUniversalTime().ToFileTimeUtc() / 10000000.0 - 11644473600.0;
                    long ownerStart = (long)Math.Floor(ownerSeconds * 1000.0);
                    if (difference != 0 || queryStatus != 0 || identity.ParentProcess.ToInt64() != ownerPid || owner.HasExited || ownerStart != expectedStart)
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
                SafeFileHandle handle = OpenInstallPath(nativePath, 0x80, Directory.Exists(nativePath) ? 3U : 1U, IntPtr.Zero, 3, 0x02200000, IntPtr.Zero);
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

        public static void StartDetached(LauncherPaths paths, string[] args)
        {
            ProcessStartInfo psi = CreateProcessStartInfo(paths, args);
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;
            using (Process.Start(psi))
            {
            }
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
        public static async Task<bool> WaitForReadyAsync(EndpointInfo endpoint, TimeSpan interval, TimeSpan total, CancellationToken token)
        {
            DateTime deadline = DateTime.UtcNow.Add(total);
            while (DateTime.UtcNow < deadline)
            {
                token.ThrowIfCancellationRequested();
                if (await IsReadyAsync(endpoint, token))
                {
                    return true;
                }
                await Task.Delay(interval, token);
            }
            return false;
        }

        public static async Task<bool> IsReadyAsync(EndpointInfo endpoint, CancellationToken token)
        {
            if (endpoint == null)
            {
                return false;
            }

            try
            {
                int statusCode = await HttpProbe.GetStatusCodeAsync(endpoint.HealthUrl, 900, token);
                return statusCode == 200;
            }
            catch
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
                List<Task<EndpointInfo>> pendingProbes = new List<Task<EndpointInfo>>(probeCount);
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
                                pendingProbes.Add(probe);
                            }
                        }
                    }

                    while (pendingProbes.Count > 0)
                    {
                        Task<EndpointInfo> completed = await Task.WhenAny(pendingProbes);
                        pendingProbes.Remove(completed);
                        EndpointInfo result = await completed;
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
                string json = await HttpProbe.GetStringAsync(url, 650, token);
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
        public static async Task<string> GetStringAsync(string url, int timeoutMs, CancellationToken token)
        {
            HttpWebRequest request = CreateRequest(url, timeoutMs);
            using (CancellationTokenSource timed = CancellationTokenSource.CreateLinkedTokenSource(token))
            {
                timed.CancelAfter(timeoutMs);
                using (timed.Token.Register(delegate { request.Abort(); }))
                {
                    try
                    {
                        using (WebResponse response = await request.GetResponseAsync())
                        using (Stream stream = response.GetResponseStream())
                        using (StreamReader reader = new StreamReader(stream ?? Stream.Null, Encoding.UTF8))
                        {
                            string body = await reader.ReadToEndAsync();
                            timed.Token.ThrowIfCancellationRequested();
                            return body;
                        }
                    }
                    catch (Exception)
                    {
                        if (!timed.IsCancellationRequested)
                        {
                            throw;
                        }
                        throw new OperationCanceledException(timed.Token);
                    }
                }
            }
        }

        public static async Task<int> GetStatusCodeAsync(string url, int timeoutMs, CancellationToken token)
        {
            HttpWebRequest request = CreateRequest(url, timeoutMs);
            using (token.Register(delegate { request.Abort(); }))
            using (WebResponse response = await request.GetResponseAsync())
            {
                HttpWebResponse http = response as HttpWebResponse;
                return http == null ? 0 : (int)http.StatusCode;
            }
        }

        private static HttpWebRequest CreateRequest(string url, int timeoutMs)
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
            request.Method = "GET";
            request.Accept = "application/json,*/*";
            request.Timeout = timeoutMs;
            request.ReadWriteTimeout = timeoutMs;
            request.KeepAlive = false;
            return request;
        }
    }

    internal static class LauncherDiagnostics
    {
        private const int BackendOutputLimitBytes = 32768;

        public static void ClearStartupFailure(LauncherPaths paths)
        {
            try
            {
                if (paths == null)
                {
                    return;
                }
                string path = Path.Combine(paths.StateDirectory, "launcher-startup-error.txt");
                if (File.Exists(path))
                {
                    File.Delete(path);
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
                if (paths == null)
                {
                    return string.Empty;
                }
                Directory.CreateDirectory(paths.StateDirectory);
                string path = Path.Combine(paths.StateDirectory, "launcher-startup-error.txt");
                StringBuilder builder = new StringBuilder();
                builder.AppendLine("SoAI launcher startup failure");
                builder.AppendLine();
                builder.AppendLine("Install root:");
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

        public static string WriteBackendExitFailure(LauncherPaths paths, int exitCode)
        {
            try
            {
                if (paths == null)
                {
                    return string.Empty;
                }
                Directory.CreateDirectory(paths.StateDirectory);
                string path = Path.Combine(paths.StateDirectory, "launcher-startup-error.txt");
                string backendLogPath = Path.Combine(paths.RootDirectory, "data", "logs", "soai-launcher.log");
                StringBuilder builder = new StringBuilder();
                builder.AppendLine("SoAI backend startup process failure");
                builder.AppendLine();
                builder.AppendLine("Backend exit code:");
                builder.AppendLine(exitCode.ToString(CultureInfo.InvariantCulture));
                builder.AppendLine();
                builder.AppendLine("Backend output log:");
                builder.AppendLine(backendLogPath);
                builder.AppendLine();
                builder.AppendLine("Recent backend output:");
                builder.AppendLine(ReadLogTail(backendLogPath));
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

        private static string ReadLogTail(string path)
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

    internal sealed class LauncherPaths
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetLongPathName(string shortPath, StringBuilder longPath, uint bufferLength);

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
        public string StateDirectory { get; private set; }
        public string FaviconPath { get; private set; }
        public string AppIconPath { get; private set; }
        public string LogoPath { get; private set; }
        public string LightLogoPath { get; private set; }
        public string FrontendDirectory { get; private set; }
        public string StandalonePythonDirectory { get; private set; }
        public string VenvScriptsDirectory { get; private set; }

        public static LauncherPaths FromExecutable()
        {
            string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            StringBuilder buffer = new StringBuilder(32768);
            uint length = GetLongPathName(ToNativeFilesystemPath(root), buffer, (uint)buffer.Capacity);
            if (length == 0 || length >= buffer.Capacity)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "The launcher installation directory cannot be resolved to its real filesystem path.");
            }
            root = buffer.ToString();
            if (root.StartsWith("\\\\?\\UNC\\", StringComparison.OrdinalIgnoreCase)) { root = "\\\\" + root.Substring(8); }
            else if (root.StartsWith("\\\\?\\", StringComparison.Ordinal)) { root = root.Substring(4); }
            LauncherPaths paths = new LauncherPaths();
            paths.RootDirectory = root;
            paths.BackendDirectory = Path.Combine(root, "backend");
            paths.BackendMain = Path.Combine(paths.BackendDirectory, "main.py");
            paths.StateDirectory = Path.Combine(root, "data", "state");
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

        public static int RunElevatedConsoleCommand(string[] args)
        {
            try
            {
                ProcessStartInfo startInfo = new ProcessStartInfo();
                startInfo.FileName = NativeBackendJob.ResolveProcessPath(Application.ExecutablePath);
                startInfo.Arguments = LauncherCommand.BuildElevatedConsoleHandoffArguments(args);
                startInfo.WorkingDirectory = NativeBackendJob.ResolveProcessPath(AppDomain.CurrentDomain.BaseDirectory, true);
                startInfo.UseShellExecute = true;
                startInfo.Verb = "runas";
                Process process = Process.Start(startInfo);
                if (process == null)
                {
                    return 1;
                }
                try
                {
                    process.WaitForExit();
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
                    Console.Error.WriteLine("Administrator access was cancelled.");
                    return 1;
                }
                Console.Error.WriteLine("Failed to start the administrator command: " + exception.Message);
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

        private static bool ValidateServerCertificate(object sender, X509Certificate certificate, X509Chain chain, SslPolicyErrors sslPolicyErrors)
        {
            if (sslPolicyErrors == SslPolicyErrors.None)
            {
                return true;
            }

            HttpWebRequest request = sender as HttpWebRequest;
            if (request != null && request.RequestUri != null && IsLoopbackHost(request.RequestUri.Host))
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
