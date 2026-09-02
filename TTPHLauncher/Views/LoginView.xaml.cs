using System.Windows.Controls;
using TTPHLauncher.ViewModels;

namespace TTPHLauncher.Views;

public partial class LoginView : UserControl
{
    public LoginView()
    {
        InitializeComponent();
    }

    // WPF's PasswordBox deliberately doesn't expose its value as a bindable
    // DependencyProperty (security measure). We bridge to the ViewModel here.
    private void PasswordBox_PasswordChanged(object sender, System.Windows.RoutedEventArgs e)
    {
        if (DataContext is LoginViewModel vm)
            vm.SetPassword(PasswordBox.Password);
    }
}
