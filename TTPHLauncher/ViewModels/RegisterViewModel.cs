using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TTPHLauncher.Services;

namespace TTPHLauncher.ViewModels;

public partial class RegisterViewModel : ObservableObject
{
    private readonly MainViewModel _main;
    private readonly ApiService _api;

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(RegisterCommand))]
    private string _username = "";

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(RegisterCommand))]
    private string _email = "";

    // Passwords set from code-behind — see RegisterView.xaml.cs
    private string _password = "";
    private string _confirmPassword = "";

    [ObservableProperty]
    private string _statusMessage = "";

    [ObservableProperty]
    private bool _isError = false;

    [ObservableProperty]
    private bool _isSuccess = false;

    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(RegisterCommand))]
    private bool _isBusy = false;

    public RegisterViewModel(MainViewModel main, ApiService api)
    {
        _main = main;
        _api = api;
    }

    public void SetPassword(string password) => _password = password;
    public void SetConfirmPassword(string password) => _confirmPassword = password;

    public void Reset()
    {
        Username = Email = "";
        _password = _confirmPassword = "";
        StatusMessage = "";
        IsError = IsSuccess = IsBusy = false;
    }

    // -----------------------------------------------------------------------
    // Commands
    // -----------------------------------------------------------------------

    [RelayCommand(CanExecute = nameof(CanRegister))]
    private async Task Register()
    {
        // Client-side validation before hitting the API
        if (_password != _confirmPassword)
        {
            StatusMessage = "Passwords do not match.";
            IsError = true;
            return;
        }
        if (_password.Length < 8)
        {
            StatusMessage = "Password must be at least 8 characters.";
            IsError = true;
            return;
        }

        IsBusy = true;
        StatusMessage = "Creating account…";
        IsError = IsSuccess = false;

        try
        {
            var result = await _api.RegisterAsync(Username.Trim(), Email.Trim(), _password);
            if (result.Success)
            {
                StatusMessage = "Account created! Taking you to sign in…";
                IsSuccess = true;
                await Task.Delay(1500);
                _main.ShowLogin();
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

    private bool CanRegister() =>
        !IsBusy
        && !string.IsNullOrWhiteSpace(Username)
        && !string.IsNullOrWhiteSpace(Email);

    [RelayCommand]
    private void GoToLogin() => _main.ShowLogin();
}
