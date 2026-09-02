using System.Windows.Controls;
using TTPHLauncher.ViewModels;

namespace TTPHLauncher.Views;

public partial class RegisterView : UserControl
{
    public RegisterView()
    {
        InitializeComponent();
    }

    private void PasswordBox_PasswordChanged(object sender, System.Windows.RoutedEventArgs e)
    {
        if (DataContext is RegisterViewModel vm)
            vm.SetPassword(PasswordBox.Password);
    }

    private void ConfirmPasswordBox_PasswordChanged(object sender, System.Windows.RoutedEventArgs e)
    {
        if (DataContext is RegisterViewModel vm)
            vm.SetConfirmPassword(ConfirmPasswordBox.Password);
    }
}
