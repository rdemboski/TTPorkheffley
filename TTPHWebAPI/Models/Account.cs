namespace TTPHWebAPI.Models;

/// <summary>
/// Represents a registered player account in the web database.
/// Note: this is separate from the Astron "AccountUD" object — the mapping
/// between Username (databaseId) and Astron's numeric accountId is managed
/// by the semidbm account-bridge file on the game server side.
/// </summary>
public class Account
{
    public int Id { get; set; }

    /// <summary>Username — used as the stable databaseId passed to the UberDOG.</summary>
    public string Username { get; set; } = string.Empty;

    public string Email { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;

    /// <summary>
    /// Access level passed to the UberDOG's LoginAccountFSM.
    /// The last digit is a 3-bit server-type mask: bit2=dev, bit1=qa, bit0=test.
    /// Hundreds digit controls staff channels: >=200=mod, >=400=admin, >=500=sysadmin.
    /// Default 507 = sysadmin + all server types (matches LocalAccountDB dev behaviour).
    /// Set to 104 for normal players on a dev server once you go live.
    /// </summary>
    public int AdminAccess { get; set; } = 507;

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? LastLogin { get; set; }

    public ICollection<PlayToken> PlayTokens { get; set; } = new List<PlayToken>();
}
