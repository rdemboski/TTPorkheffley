using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TTPHLauncher.Services;

namespace TTPHLauncher.ViewModels;

public partial class LoginViewModel : ObservableObject
{
    private readonly MainViewModel _main;
    private readonly ApiService _api;

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(LoginCommand))]
    private string _username = "";

    // Password is set from code-behind via SetPassword() because WPF's
    // PasswordBox intentionally doesn't support two-way binding for security.
    private string _password = "";

    [ObservableProperty]
    private string _statusMessage = "";

    [ObservableProperty]
    private bool _isError = false;

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(LoginCommand))]
    private bool _isBusy = false;

    public LoginViewModel(MainViewModel main, ApiService api)
    {
        _main = main;
        _api = api;
    }

    /// <summary>Called from LoginView.xaml.cs PasswordChanged handler.</summary>
    public void SetPassword(string password) => _password = password;

    public void Reset()
    {
        Username = "";
        _password = "";
        StatusMessage = "";
        IsError = false;
        IsBusy = false;
    }

    // -----------------------------------------------------------------------
    // Commands
    // -----------------------------------------------------------------------

    [RelayCommand(CanExecute = nameof(CanLogin))]
    private async Task Login()
    {
        IsBusy = true;
        StatusMessage = "Signing in…";
        IsError = false;

        try
        {
            var result = await _api.LoginAsync(Username.Trim(), _password);
            if (result.Success)
            {
                _main.ShowPatcher(result.PlayToken!, result.GameServer!);
            }
            else
            {
                StatusMessage = result.Message;
                IsError = true;
            }
        }
        catch (Exception)
        {
            StatusMessage = "Could not reach the game server. Is TTPHWebAPI running?";
            IsError = true;
        }
        finally
        {
            IsBusy = false;
        }
    }

    private bool CanLogin() => !IsBusy && !string.IsNullOrWhiteSpace(Username);

    [RelayCommand]
    private void GoToRegister() => _main.ShowRegister();
}
