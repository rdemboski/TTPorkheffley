using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TTPHLauncher.Models;
using TTPHLauncher.Services;

namespace TTPHLauncher.ViewModels;

/// <summary>
/// Root ViewModel bound to MainWindow.
/// Owns navigation between Login, Register and Patcher screens,
/// and the custom title-bar commands (minimize / close).
/// </summary>
public partial class MainViewModel : ObservableObject
{
    // Child ViewModels — created once and reused so state persists during navigation.
    private readonly LoginViewModel _loginVm;
    private readonly RegisterViewModel _registerVm;
    private readonly PatcherViewModel _patcherVm;

    [ObservableProperty]
    private ObservableObject _currentView;

    public MainViewModel()
    {
        var api = new ApiService();
        var patcher = new PatcherService();

        _loginVm = new LoginViewModel(this, api);
        _registerVm = new RegisterViewModel(this, api);
        _patcherVm = new PatcherViewModel(this, api, patcher);

        _currentView = _loginVm;
    }

    // -----------------------------------------------------------------------
    // Navigation
    // -----------------------------------------------------------------------

    public void ShowLogin()
    {
        _loginVm.Reset();
        CurrentView = _loginVm;
    }

    public void ShowRegister()
    {
        _registerVm.Reset();
        CurrentView = _registerVm;
    }

    /// <summary>
    /// Called by LoginViewModel after a successful login.
    /// Passes the play token and game server to the patcher so it can launch
    /// the game when patching completes.
    /// </summary>
    public void ShowPatcher(string playToken, string gameServer)
    {
        var overrride = LauncherConfig.Instance.GameServerOverride;
        if (!string.IsNullOrWhiteSpace(overrride))
            gameServer = overrride;

        _patcherVm.Initialize(playToken, gameServer);
        CurrentView = _patcherVm;
    }

    // -----------------------------------------------------------------------
    // Window chrome commands (bound to the custom title bar buttons)
    // -----------------------------------------------------------------------

    [RelayCommand]
    private static void Minimize() =>
        Application.Current.MainWindow.WindowState = WindowState.Minimized;

    [RelayCommand]
    private static void Close() =>
        Application.Current.Shutdown();
}
