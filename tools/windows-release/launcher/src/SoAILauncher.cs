using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
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
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography.X509Certificates;
using System.Security.Principal;
using System.Text;
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
            LoopbackCertificatePolicy.Install();
            LauncherPaths paths = LauncherPaths.FromExecutable();
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
                    return BackendProcess.RunForeground(paths, LauncherCommand.RemoveElevatedConsoleHandoff(args));
                }
                catch (Exception exception)
                {
                    LauncherDiagnostics.WriteStartupFailure(paths, exception);
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
                    return BackendProcess.RunForeground(paths, args);
                }
                catch (Exception ex)
                {
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
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (LauncherForm form = new LauncherForm(paths, args))
            {
                Application.Run(form);
                return form.ExitCode;
            }
        }
    }

    internal static class LauncherCommand
    {
        private const string ElevatedConsoleHandoffArgument = "--soai-elevated-console-command";

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

        private readonly LauncherPaths paths;
        private readonly string[] originalArgs;
        private readonly SplashView splash;
        private readonly WebView2 webView;
        private readonly CancellationTokenSource shutdownToken;
        private readonly List<DetachedWebViewForm> detachedWindows;
        private CoreWebView2Environment webViewEnvironment;
        private EndpointInfo activeEndpoint;
        private bool closeRequested;

        public int ExitCode { get; private set; }

        public LauncherForm(LauncherPaths paths, string[] args)
        {
            this.paths = paths;
            this.originalArgs = args ?? new string[0];
            this.shutdownToken = new CancellationTokenSource();
            this.detachedWindows = new List<DetachedWebViewForm>();
            this.ExitCode = 0;

            this.Text = "SoAI";
            this.StartPosition = FormStartPosition.CenterScreen;
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.MinimumSize = new Size(980, 680);
            this.Size = new Size(1320, 860);
            this.BackColor = Color.FromArgb(21, 21, 21);
            this.Icon = paths.TryLoadIcon();

            this.webView = new WebView2();
            this.webView.Dock = DockStyle.Fill;
            this.webView.Visible = true;
            this.Controls.Add(this.webView);

            this.splash = new SplashView(paths);
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
                splash.SetStatus("Preparing the app window...");
                await EnsureWebViewAsync();

                splash.SetStatus("Starting SoAI...");
                EndpointInfo endpoint = await EnsureBackendAsync(shutdownToken.Token);

                splash.SetStatus("Preparing the app window...");
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
                splash.ShowFailure(BuildStartupFailureMessage(ex, diagnosticPath));
            }
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
                splash.SetStatus("SoAI is already running...");
                return existingEndpoint;
            }

            splash.SetStatus("Requesting administrator access for the SoAI runtime...");
            using (ElevatedBackendSession session = await ElevatedBackendSession.StartAsync(paths, BuildStartArguments(originalArgs), token))
            {
                return await session.WaitForReadyAsync(splash, BackendStartupTimeout, token);
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
                window = new DetachedWebViewForm(owner.Icon);
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

            splash.SetStatus("Opening SoAI...");
            await WaitForFrontendReadyAsync(token);

            webView.BringToFront();
            splash.BringToFront();
            splash.BeginExit();
            await Task.Delay(320, token);
            splash.Visible = false;
            Controls.Remove(splash);
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
            DateTime deadline = DateTime.UtcNow.AddSeconds(60);
            while (DateTime.UtcNow < deadline)
            {
                token.ThrowIfCancellationRequested();
                Task<string> scriptTask = webView.CoreWebView2.ExecuteScriptAsync(
                    "(function(){var d=document.documentElement;var p=document.getElementById('page-preloader');var login=document.querySelector('form,input[name=\"username\"],#username,[autocomplete=\"username\"]');return !!(document.readyState==='complete' && ((!d || !d.hasAttribute('data-soai-boot-state')) || login) && (!p || !p.isConnected || p.classList.contains('page-preloader--exiting') || login));})()");
                Task completed = await Task.WhenAny(scriptTask, Task.Delay(1000, token));
                if (completed != scriptTask)
                {
                    continue;
                }
                string result = await scriptTask;
                if (string.Equals(result, "true", StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
                await Task.Delay(250, token);
            }

            throw new TimeoutException("The SoAI WebUI loaded, but the app did not become interactive within 60 seconds.");
        }

        private void OnFormClosing(object sender, FormClosingEventArgs e)
        {
            if (closeRequested)
            {
                return;
            }

            closeRequested = true;
            shutdownToken.Cancel();
            CloseDetachedWindows();
        }

        private void CloseQuietly()
        {
            closeRequested = true;
            CloseDetachedWindows();
            Close();
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
        private readonly System.Windows.Forms.Timer timer;
        private readonly Image logo;
        private float angle;
        private string status;
        private bool failed;
        private bool warning;
        private bool exiting;
        private float introProgress;
        private float exitProgress;

        public SplashView(LauncherPaths paths)
        {
            this.DoubleBuffered = true;
            this.logo = paths.TryLoadLogo();
            this.status = "Starting SoAI...";
            this.timer = new System.Windows.Forms.Timer();
            this.timer.Interval = 16;
            this.timer.Tick += delegate
            {
                angle = (angle + 4.0f) % 360.0f;
                if (!failed && !exiting)
                {
                    introProgress = Math.Min(1.0f, introProgress + 0.018f);
                }
                if (exiting)
                {
                    exitProgress = Math.Min(1.0f, exitProgress + 0.055f);
                }
                Invalidate();
            };
            this.timer.Start();
        }

        public void SetStatus(string value)
        {
            SetStatus(value, false);
        }

        public void SetStatus(string value, bool isWarning)
        {
            if (failed)
            {
                return;
            }
            status = string.IsNullOrWhiteSpace(value) ? "Starting SoAI..." : value.Trim();
            warning = isWarning;
            Invalidate();
        }

        public void ShowFailure(string message)
        {
            failed = true;
            timer.Stop();
            warning = false;
            status = "SoAI could not start." + Environment.NewLine + (message ?? string.Empty).Trim();
            Invalidate();
        }

        public void BeginExit()
        {
            exiting = true;
            exitProgress = 0.0f;
            Invalidate();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            using (LinearGradientBrush bg = new LinearGradientBrush(ClientRectangle, Color.FromArgb(33, 33, 33), Color.FromArgb(20, 20, 20), LinearGradientMode.Horizontal))
            {
                g.FillRectangle(bg, ClientRectangle);
            }

            float centerX = ClientSize.Width / 2.0f;
            float opacity = exiting ? Math.Max(0.0f, 1.0f - exitProgress) : 1.0f;
            float logoIntro = failed ? 1.0f : EaseOut(Clamp01(introProgress / 0.62f));
            float statusIntro = failed ? 1.0f : EaseOut(Clamp01((introProgress - 0.10f) / 0.72f));
            float spinnerIntro = EaseOut(Clamp01((introProgress - 0.04f) / 0.96f));
            float logoWidth = Math.Min(ClientSize.Width * 0.80f, 420.0f);
            float logoHeight = logo == null ? (logoWidth * 750.0f / 1800.0f) : logoWidth * logo.Height / Math.Max(1.0f, (float)logo.Width);
            float spinnerSize = 78.0f;
            float statusHeight = failed ? Math.Min(260.0f, Math.Max(150.0f, ClientSize.Height * 0.32f)) : 20.0f;
            float gap = 30.0f;
            float logoMarginCorrection = logoWidth * 39.0f / 382.0f / 2.4f;
            float spinnerAreaHeight = failed ? 0.0f : gap + spinnerSize;
            float groupHeight = logoHeight - logoMarginCorrection + gap + statusHeight + spinnerAreaHeight;
            float top = (ClientSize.Height - groupHeight) / 2.0f;

            if (logo != null)
            {
                RectangleF logoRect = new RectangleF(centerX - logoWidth / 2.0f, top - (24.0f * (1.0f - logoIntro)), logoWidth, logoHeight);
                DrawImageWithOpacity(g, logo, logoRect, opacity * logoIntro);
            }

            float statusTop = top + logoHeight - logoMarginCorrection + gap - (12.0f * (1.0f - statusIntro));
            RectangleF textRect = new RectangleF(Math.Max(24, centerX - 330), statusTop, Math.Min(660, ClientSize.Width - 48), statusHeight);
            using (Font font = new Font("Segoe UI", failed ? 10.0f : 9.5f, FontStyle.Regular))
            using (Brush brush = new SolidBrush(ResolveStatusColor(opacity, statusIntro)))
            using (StringFormat format = new StringFormat())
            {
                format.Alignment = StringAlignment.Center;
                format.LineAlignment = StringAlignment.Near;
                format.Trimming = StringTrimming.EllipsisWord;
                format.FormatFlags = StringFormatFlags.LineLimit;
                g.DrawString(status, font, brush, textRect, format);
            }

            if (!failed)
            {
                float spinnerTop = top + logoHeight - logoMarginCorrection + gap + statusHeight + gap;
                RectangleF spinnerRect = new RectangleF(centerX - spinnerSize / 2.0f, spinnerTop, spinnerSize, spinnerSize);
                using (Pen basePen = new Pen(Color.FromArgb((int)(38 * opacity * spinnerIntro), 230, 230, 230), 4.0f))
                using (Pen arcPen = new Pen(Color.FromArgb((int)(255 * opacity * spinnerIntro), 134, 179, 30), 4.0f))
                {
                    g.DrawEllipse(basePen, spinnerRect);
                    g.DrawArc(arcPen, spinnerRect, angle, 88.0f);
                }
            }
        }

        private Color ResolveStatusColor(float opacity, float statusIntro)
        {
            if (failed)
            {
                return Color.FromArgb(255, 225, 140, 140);
            }
            int alpha = (int)((warning ? 235 : 174) * opacity * statusIntro);
            if (warning)
            {
                return Color.FromArgb(alpha, 255, 177, 84);
            }
            return Color.FromArgb(alpha, 230, 230, 230);
        }

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
            using (System.Drawing.Imaging.ImageAttributes attributes = new System.Drawing.Imaging.ImageAttributes())
            {
                System.Drawing.Imaging.ColorMatrix matrix = new System.Drawing.Imaging.ColorMatrix();
                matrix.Matrix33 = Math.Max(0.0f, Math.Min(1.0f, opacity));
                attributes.SetColorMatrix(matrix, System.Drawing.Imaging.ColorMatrixFlag.Default, System.Drawing.Imaging.ColorAdjustType.Bitmap);
                g.DrawImage(image, Rectangle.Round(rect), 0, 0, image.Width, image.Height, GraphicsUnit.Pixel, attributes);
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                timer.Dispose();
                if (logo != null)
                {
                    logo.Dispose();
                }
            }
            base.Dispose(disposing);
        }
    }

    internal sealed class DetachedWebViewForm : Form
    {
        private bool hiddenUntilContent;

        public DetachedWebViewForm(Icon icon)
        {
            Text = "SoAI";
            StartPosition = FormStartPosition.CenterParent;
            MinimumSize = new Size(860, 620);
            Size = new Size(1120, 760);
            BackColor = Color.FromArgb(21, 21, 21);
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
            Controls.Add(WebView);
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

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            FullScreenMode.Set(this, false);
            base.OnFormClosing(e);
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
                StartFromDesktopShell(paths, forwarded.ToArray());
                return true;
            }
            catch (Exception exception)
            {
                LauncherDiagnostics.WriteStartupFailure(paths, exception);
                MessageBox.Show("SoAI could not start in the standard desktop session. Start SoAI from its desktop shortcut.", "SoAI", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return false;
            }
        }

        private static void StartFromDesktopShell(LauncherPaths paths, string[] args)
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
                if (!CreateProcess(executable, commandLine, IntPtr.Zero, IntPtr.Zero, false, CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT, IntPtr.Zero, paths.RootDirectory, ref startupInformation, out processInformation))
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
        private readonly NamedPipeServerStream pipe;
        private readonly StreamReader reader;
        private readonly StreamWriter writer;
        private readonly Process helperProcess;
        private bool ready;

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
                startInfo.FileName = Application.ExecutablePath;
                startInfo.Arguments = BackendProcess.Quote(HelperArgument)
                    + " " + BackendProcess.Quote(pipeName)
                    + " " + BackendProcess.Quote(authenticationToken)
                    + BackendProcess.BuildArgumentString(backendArgs);
                startInfo.WorkingDirectory = paths.RootDirectory;
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

        public void Dispose()
        {
            try
            {
                if (!ready)
                {
                    TryCancel();
                }
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

    internal static class ElevatedBackendHelper
    {
        private const string HelperArgument = "--soai-elevated-backend-helper";

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
                await CompleteOwnershipTransferAsync(reader, writer);
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
                        writer.WriteLine("ERROR\tSoAI stopped before it became ready.");
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
                        backend.Commit();
                        await CompleteOwnershipTransferAsync(reader, writer);
                        return 0;
                    }
                    writer.WriteLine("STATUS\tWaiting for SoAI to become ready...");
                    await Task.Delay(500);
                }
                writer.WriteLine("ERROR\tSoAI backend startup timed out.");
                return 1;
            }
        }

        private static async Task CompleteOwnershipTransferAsync(StreamReader reader, StreamWriter writer)
        {
            writer.WriteLine("COMMITTED");
            string trailingMessage = await reader.ReadLineAsync();
            if (trailingMessage != null)
            {
                throw new InvalidOperationException("The launcher sent data after completing startup ownership transfer.");
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

    internal sealed class NativeBackendJob : IDisposable
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
        private const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
        private const int JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9;
        private readonly Process process;
        private IntPtr jobHandle;

        private NativeBackendJob(Process process, IntPtr jobHandle)
        {
            this.process = process;
            this.jobHandle = jobHandle;
        }

        public bool HasExited { get { return process.HasExited; } }

        public static NativeBackendJob Start(LauncherPaths paths, string[] args)
        {
            string python = BackendProcess.ResolvePython(paths, args);
            BackendProcess.RequireBackendMain(paths);
            BackendProcess.ConfigureBackendEnvironment(paths);
            STARTUPINFO startupInfo = new STARTUPINFO();
            startupInfo.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            startupInfo.dwFlags = STARTF_USESHOWWINDOW | STARTF_USESTDHANDLES;
            startupInfo.wShowWindow = 0;
            PROCESS_INFORMATION processInfo;
            StringBuilder commandLine = new StringBuilder(BackendProcess.Quote(python) + " " + BackendProcess.Quote(paths.BackendMain) + BackendProcess.BuildArgumentString(args));
            string logDirectory = Path.Combine(paths.RootDirectory, "data", "logs");
            Directory.CreateDirectory(logDirectory);
            using (SafeFileHandle input = OpenNullInput())
            using (FileStream output = new FileStream(Path.Combine(logDirectory, "soai-launcher.log"), FileMode.Append, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete))
            {
                startupInfo.hStdInput = input.DangerousGetHandle();
                startupInfo.hStdOutput = output.SafeFileHandle.DangerousGetHandle();
                startupInfo.hStdError = startupInfo.hStdOutput;
                RequireInheritableHandle(startupInfo.hStdInput);
                RequireInheritableHandle(startupInfo.hStdOutput);
                if (!CreateProcess(python, commandLine, IntPtr.Zero, IntPtr.Zero, true, CREATE_SUSPENDED | CREATE_NO_WINDOW, IntPtr.Zero, paths.RootDirectory, ref startupInfo, out processInfo))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to create the administrator backend process.");
                }
            }
            IntPtr job = IntPtr.Zero;
            try
            {
                job = CreateJobObject(IntPtr.Zero, null);
                if (job == IntPtr.Zero)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to create the backend rollback job.");
                }
                SetKillOnJobClose(job, true);
                if (!AssignProcessToJobObject(job, processInfo.hProcess))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to assign the backend process to its rollback job.");
                }
                if (ResumeThread(processInfo.hThread) == UInt32.MaxValue)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to resume the backend process.");
                }
                Process process = Process.GetProcessById(processInfo.dwProcessId);
                CloseHandle(processInfo.hThread);
                CloseHandle(processInfo.hProcess);
                return new NativeBackendJob(process, job);
            }
            catch
            {
                if (job != IntPtr.Zero)
                {
                    CloseHandle(job);
                }
                TerminateProcess(processInfo.hProcess, 1);
                CloseHandle(processInfo.hThread);
                CloseHandle(processInfo.hProcess);
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
            SafeFileHandle handle = CreateFile("NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
            if (handle.IsInvalid)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Failed to open the hidden backend input device.");
            }
            return handle;
        }

        public void Commit()
        {
            SetKillOnJobClose(jobHandle, false);
        }

        public void Dispose()
        {
            process.Dispose();
            if (jobHandle != IntPtr.Zero)
            {
                CloseHandle(jobHandle);
                jobHandle = IntPtr.Zero;
            }
        }

        private static void SetKillOnJobClose(IntPtr job, bool enabled)
        {
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION information = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            information.BasicLimitInformation.LimitFlags = enabled ? JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE : 0;
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
        private static extern SafeFileHandle CreateFile(string fileName, uint desiredAccess, uint shareMode, IntPtr securityAttributes, uint creationDisposition, uint flagsAndAttributes, IntPtr templateFile);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateJobObject(IntPtr jobAttributes, string name);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

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
            if (!File.Exists(python))
            {
                throw new FileNotFoundException("The bundled Python 3.13 runtime is missing or damaged. Please reinstall SoAI.", python);
            }
            RequireBackendMain(paths);

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = python;
            psi.Arguments = Quote(paths.BackendMain) + BuildArgumentString(args);
            psi.WorkingDirectory = paths.RootDirectory;
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
            if (!File.Exists(paths.BackendMain))
            {
                throw new FileNotFoundException("SoAI backend entrypoint was not found.", paths.BackendMain);
            }
        }

        internal static void ConfigureBackendEnvironment(LauncherPaths paths)
        {
            Environment.SetEnvironmentVariable("PATH", BuildProcessPath(paths, Environment.GetEnvironmentVariable("PATH")));
            Environment.SetEnvironmentVariable("SOAI_GUI_LAUNCHED", "1");
            Environment.SetEnvironmentVariable("SOAI_NO_BROWSER", "1");
            Environment.SetEnvironmentVariable("PYTHONUTF8", "1");
            Environment.SetEnvironmentVariable("PYTHONIOENCODING", "utf-8");
        }

        private static void ApplyBackendEnvironment(LauncherPaths paths, System.Collections.Specialized.StringDictionary environment)
        {
            environment["PATH"] = BuildProcessPath(paths, environment["PATH"]);
            environment["SOAI_GUI_LAUNCHED"] = "1";
            environment["SOAI_NO_BROWSER"] = "1";
            environment["PYTHONUTF8"] = "1";
            environment["PYTHONIOENCODING"] = "utf-8";
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
            if (!string.IsNullOrWhiteSpace(path) && Directory.Exists(path))
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
            DateTime deadline = DateTime.UtcNow.Add(total);
            while (DateTime.UtcNow < deadline)
            {
                token.ThrowIfCancellationRequested();
                EndpointInfo endpoint = await TryResolveAsync(token);
                if (endpoint != null)
                {
                    return endpoint;
                }
                await Task.Delay(interval, token);
            }
            return null;
        }

        public static async Task<EndpointInfo> TryResolveAsync(CancellationToken token)
        {
            List<Task<EndpointInfo>> probes = new List<Task<EndpointInfo>>();
            foreach (string host in Hosts)
            {
                foreach (int port in Ports)
                {
                    foreach (string scheme in Schemes)
                    {
                        probes.Add(ProbeOneAsync(scheme, host, port, token));
                    }
                }
            }

            while (probes.Count > 0)
            {
                Task<EndpointInfo> completed = await Task.WhenAny(probes);
                probes.Remove(completed);
                EndpointInfo result = await completed;
                if (result != null)
                {
                    return result;
                }
            }
            return null;
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
                throw;
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
            using (token.Register(delegate { request.Abort(); }))
            using (WebResponse response = await request.GetResponseAsync())
            using (Stream stream = response.GetResponseStream())
            using (StreamReader reader = new StreamReader(stream ?? Stream.Null, Encoding.UTF8))
            {
                return await reader.ReadToEndAsync();
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
    }

    internal sealed class LauncherPaths
    {
        public string RootDirectory { get; private set; }
        public string BackendMain { get; private set; }
        public string StateDirectory { get; private set; }
        public string FaviconPath { get; private set; }
        public string AppIconPath { get; private set; }
        public string LogoPath { get; private set; }
        public string StandalonePythonDirectory { get; private set; }
        public string VenvScriptsDirectory { get; private set; }

        public static LauncherPaths FromExecutable()
        {
            string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            LauncherPaths paths = new LauncherPaths();
            paths.RootDirectory = root;
            paths.BackendMain = Path.Combine(root, "backend", "main.py");
            paths.StateDirectory = Path.Combine(root, "data", "state");
            paths.FaviconPath = Path.Combine(root, "frontend", "favicon.ico");
            paths.AppIconPath = Path.Combine(root, "soai-app.ico");
            paths.LogoPath = Path.Combine(root, "frontend", "assets", "img", "soai", "soai-logo-dark.png");
            paths.StandalonePythonDirectory = Path.Combine(root, "python");
            paths.VenvScriptsDirectory = Path.Combine(root, "soai_main_venv", "Scripts");
            return paths;
        }

        public string ResolveLaunchPythonExecutable()
        {
            ResolveBootstrapPythonExecutable();

            string venvPath = Path.Combine(RootDirectory, "soai_main_venv");
            string venvPython = Path.Combine(RootDirectory, "soai_main_venv", "Scripts", "python.exe");
            if (!Directory.Exists(venvPath) || !File.Exists(venvPython))
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
            if (!File.Exists(bootstrapPython) || !IsUsablePythonExecutable(bootstrapPython))
            {
                throw new FileNotFoundException("The bundled Python 3.13 runtime is missing or damaged. Please reinstall SoAI.", bootstrapPython);
            }
            return bootstrapPython;
        }

        private string ResolveStandalonePythonExecutable()
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
                if (File.Exists(candidate))
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
                psi.FileName = python;
                psi.Arguments = "--version";
                psi.WorkingDirectory = Path.GetDirectoryName(python) ?? Environment.CurrentDirectory;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
                Process process = Process.Start(psi);
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

        public Image TryLoadLogo()
        {
            try
            {
                if (File.Exists(LogoPath))
                {
                    return Image.FromFile(LogoPath);
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
                startInfo.FileName = Application.ExecutablePath;
                startInfo.Arguments = LauncherCommand.BuildElevatedConsoleHandoffArguments(args);
                startInfo.WorkingDirectory = AppDomain.CurrentDomain.BaseDirectory;
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
