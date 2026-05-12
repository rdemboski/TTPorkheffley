namespace TTPHWebAPI.Services;

public interface IAccountService
{
    Task<(bool Success, string Message)> RegisterAsync(
        string username, string email, string password);

    Task<(bool Success, string? Token, string? GameServer, string Message)> LoginAsync(
        string username, string password);

    Task<ValidateTokenResult> ValidateTokenAsync(string token);
}

/// <summary>Intermediate result from token validation (before assembling the HTTP response).</summary>
public record ValidateTokenResult(
    bool Success,
    string? DatabaseId,
    int AdminAccess,
    string? Reason);
