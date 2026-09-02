namespace TTPHWebAPI.Models;

/// <summary>
/// A short-lived session token issued at login and consumed by the game's UberDOG
/// to authenticate the connecting client.
/// </summary>
public class PlayToken
{
    public int Id { get; set; }

    public int AccountId { get; set; }
    public Account Account { get; set; } = null!;

    /// <summary>The raw GUID string set as TTR_PLAYCOOKIE and sent by the game client.</summary>
    public string Token { get; set; } = string.Empty;

    public DateTime IssuedAt { get; set; } = DateTime.UtcNow;
    public DateTime ExpiresAt { get; set; }

    /// <summary>True once the token is revoked (new login issued, or admin action).</summary>
    public bool IsRevoked { get; set; } = false;
}
