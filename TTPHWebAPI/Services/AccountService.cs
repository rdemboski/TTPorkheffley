using Microsoft.EntityFrameworkCore;
using TTPHWebAPI.Data;
using TTPHWebAPI.Models;

namespace TTPHWebAPI.Services;

public class AccountService : IAccountService
{
    private readonly AppDbContext _db;
    private readonly IConfiguration _config;
    private readonly ILogger<AccountService> _logger;

    public AccountService(AppDbContext db, IConfiguration config, ILogger<AccountService> logger)
    {
        _db = db;
        _config = config;
        _logger = logger;
    }

    public async Task<(bool Success, string Message)> RegisterAsync(
        string username, string email, string password)
    {
        username = username.Trim();
        email = email.Trim().ToLowerInvariant();

        if (string.IsNullOrWhiteSpace(username) || username.Length < 3 || username.Length > 32)
            return (false, "Username must be 3–32 characters.");

        if (password.Length < 8)
            return (false, "Password must be at least 8 characters.");

        if (await _db.Accounts.AnyAsync(a => a.Username == username))
            return (false, "That username is already taken.");

        if (await _db.Accounts.AnyAsync(a => a.Email == email))
            return (false, "An account with that email already exists.");

        var account = new Account
        {
            Username = username,
            Email = email,
            PasswordHash = BCrypt.Net.BCrypt.HashPassword(password),
        };

        _db.Accounts.Add(account);
        await _db.SaveChangesAsync();

        _logger.LogInformation("Registered new account: {Username}", username);
        return (true, "Account created successfully.");
    }

    public async Task<(bool Success, string? Token, string? GameServer, string Message)> LoginAsync(
        string username, string password)
    {
        username = username.Trim();
        var account = await _db.Accounts.FirstOrDefaultAsync(a => a.Username == username);

        if (account == null || !BCrypt.Net.BCrypt.Verify(password, account.PasswordHash))
            return (false, null, null, "Invalid username or password.");

        // Revoke any still-active tokens for this account so only one session
        // can be in-flight at a time. The UberDOG also ejects duplicate sessions
        // via CLIENTAGENT_EJECT, but this stops stale tokens from redeeming.
        var activeTokens = await _db.PlayTokens
            .Where(t => t.AccountId == account.Id && !t.IsRevoked && t.ExpiresAt > DateTime.UtcNow)
            .ToListAsync();
        foreach (var old in activeTokens)
            old.IsRevoked = true;

        var lifetimeHours = _config.GetValue("TokenLifetimeHours", 24);
        var playToken = new PlayToken
        {
            AccountId = account.Id,
            Token = Guid.NewGuid().ToString("N"), // 32-char hex, no hyphens
            IssuedAt = DateTime.UtcNow,
            ExpiresAt = DateTime.UtcNow.AddHours(lifetimeHours),
        };
        _db.PlayTokens.Add(playToken);

        account.LastLogin = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        var gameServer = _config["GameServer"] ?? "127.0.0.1:7198";
        _logger.LogInformation("Issued play token to {Username}, expires {ExpiresAt}",
            username, playToken.ExpiresAt);

        return (true, playToken.Token, gameServer, "Login successful.");
    }

    public async Task<ValidateTokenResult> ValidateTokenAsync(string token)
    {
        var playToken = await _db.PlayTokens
            .Include(t => t.Account)
            .FirstOrDefaultAsync(t => t.Token == token);

        if (playToken == null)
            return new ValidateTokenResult(false, null, 0, "Token not found.");

        if (playToken.IsRevoked)
            return new ValidateTokenResult(false, null, 0, "Token has been revoked.");

        if (playToken.ExpiresAt < DateTime.UtcNow)
            return new ValidateTokenResult(false, null, 0, "Token has expired. Please log in again.");

        _logger.LogInformation("Validated token for account {Username}", playToken.Account.Username);

        return new ValidateTokenResult(
            Success: true,
            DatabaseId: playToken.Account.Username,
            AdminAccess: playToken.Account.AdminAccess,
            Reason: null);
    }
}
