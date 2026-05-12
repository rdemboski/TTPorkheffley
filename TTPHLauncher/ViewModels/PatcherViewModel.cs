using System.Diagnostics;
using System.IO;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TTPHLauncher.Models;
using TTPHLauncher.Services;

namespace TTPHLauncher.ViewModels;

public partial class PatcherViewModel : ObservableObject
{
    private readonly MainViewModel _main;
    private readonly ApiService _api;
    private readonly PatcherService _patcher;

    private string _playToken = "";
    private string _gameServer = "";

    [ObservableProperty]
    private string _statusText = "Checking for updates…";

    [ObservableProperty]
    private double _overallProgress = 0; // 0–100

    [ObservableProperty]
    private double _fileProgress = 0; // 0–100, current file

    [ObservableProperty]
    private bool _isPatching = true;

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(PlayCommand))]
    private bool _canPlay = false;

    [ObservableProperty]
    private bool _hasError = false;

    [ObservableProperty]
    private string _currentFileName = "";

    public PatcherViewModel(MainViewModel main, ApiService api, PatcherService patcher)
    {
        _main = main;
        _api = api;
        _patcher = patcher;
    }

    /// <summary>Called by MainViewModel.ShowPatcher() before navigating here.</summary>
    public void Initialize(string playToken, string gameServer)
    {
        _playToken = playToken;
        _gameServer = gameServer;

        // Reset state each time we enter this view
        OverallProgress = 0;
        FileProgress = 0;
        IsPatching = true;
        CanPlay = false;
        HasError = false;
        StatusText = "Checking for updates…";
        CurrentFileName = "";

        // Kick off the async patch check (fire-and-forget; errors are caught inside)
        _ = RunPatcherAsync();
    }

    // -----------------------------------------------------------------------
    // Patcher logic
    // -----------------------------------------------------------------------

    private async Task RunPatcherAsync()
    {
        try
        {
            var config = LauncherConfig.Instance;

            if (!config.PatcherEnabled)
            {
                // No CDN configured — skip patching and go straight to ready.
                StatusText = "No patcher configured. Ready to play!";
                OverallProgress = 100;
                IsPatching = false;
                CanPlay = true;
                return;
            }

            // 1. Fetch manifest
            StatusText = "Fetching manifest…";
            string manifestText;
            try
            {
                manifestText = await _api.GetManifestAsync();
            }
            catch
            {
                SetError("Could not download the game manifest. Is TTPHWebAPI running?");
                return;
            }

            // 2. Parse manifest
            var files = _patcher.ParseManifest(manifestText);
            if (files.Count == 0)
            {
                // Manifest is empty or has placeholder 0-byte entries — nothing to patch.
                StatusText = "Game files are up to date!";
                OverallProgress = 100;
                IsPatching = false;
                CanPlay = true;
                return;
            }

            // 3. Identify which files need downloading
            var toDownload = files.Where(f => !_patcher.IsFileUpToDate(f)).ToList();

            if (toDownload.Count == 0)
            {
                StatusText = "Game files are up to date!";
                OverallProgress = 100;
                IsPatching = false;
                CanPlay = true;
                return;
            }

            // 4. Download each file, updating progress
            for (int i = 0; i < toDownload.Count; i++)
            {
                var file = toDownload[i];
                CurrentFileName = file.Filename;
                FileProgress = 0;

                double basePercent = (double)i / toDownload.Count * 100;
                double perFile = 100.0 / toDownload.Count;

                StatusText = $"Downloading {file.Filename}… (file {i + 1} of {toDownload.Count})";

                var progress = new Progress<(long Downloaded, long Total)>(p =>
                {
                    if (p.Total <= 0) return;
                    FileProgress = (double)p.Downloaded / p.Total * 100;
                    OverallProgress = basePercent + FileProgress / 100.0 * perFile;
                });

                try
                {
                    await _patcher.DownloadFileAsync(file, progress);
                }
                catch (Exception ex)
                {
                    SetError($"Failed to download {file.Filename}: {ex.Message}");
                    return;
                }

                OverallProgress = basePercent + perFile;
            }

            // 5. Done
            StatusText = "All files are up to date!";
            OverallProgress = 100;
            FileProgress = 100;
            IsPatching = false;
            CanPlay = true;
        }
        catch (Exception ex)
        {
            SetError($"Unexpected patcher error: {ex.Message}");
        }
    }

    private void SetError(string message)
    {
        StatusText = message;
        HasError = true;
        IsPatching = false;
    }

    // -----------------------------------------------------------------------
    // Commands
    // -----------------------------------------------------------------------

    [RelayCommand(CanExecute = nameof(CanPlay))]
    private void Play()
    {
        var config = LauncherConfig.Instance;
        var exePath = Path.IsPathRooted(config.GameExecutable)
            ? config.GameExecutable
            : Path.Combine(config.ResolvedGameDirectory, config.GameExecutable);

        if (!File.Exists(exePath))
        {
            StatusText = $"Game executable not found: {exePath}";
            HasError = true;
            return;
        }

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = "--game",
                UseShellExecute = false,
                WorkingDirectory = Path.GetDirectoryName(exePath) ?? config.ResolvedGameDirectory,
            };

            // Pass credentials via environment variables — TTRLauncher reads these.
            psi.Environment["TTR_PLAYCOOKIE"] = _playToken;
            psi.Environment["TTR_GAMESERVER"] = _gameServer;

            Process.Start(psi);

            // Close the launcher once the game starts.
            System.Windows.Application.Current.Shutdown();
        }
        catch (Exception ex)
        {
            StatusText = $"Failed to launch game: {ex.Message}";
            HasError = true;
        }
    }

    [RelayCommand]
    private void RetryPatch()
    {
        HasError = false;
        IsPatching = true;
        CanPlay = false;
        _ = RunPatcherAsync();
    }

    [RelayCommand]
    private void SignOut() => _main.ShowLogin();
}
