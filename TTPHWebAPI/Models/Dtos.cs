namespace TTPHWebAPI.Models;

// ---------------------------------------------------------------------------
// Inbound request DTOs
// ---------------------------------------------------------------------------

public record RegisterRequest(
    string Username,
    string Email,
    string Password);

public record LoginRequest(
    string Username,
    string Password);

/// <summary>
/// Sent by the Python UberDOG's WebAccountDB to validate a play token.
/// </summary>
public record ValidateTokenRequest(string Token);

// ---------------------------------------------------------------------------
// Outbound response DTOs
// ---------------------------------------------------------------------------

public record RegisterResponse(bool Success, string Message);

/// <summary>
/// Returned to the launcher after a successful login.
/// The launcher sets TTR_PLAYCOOKIE = PlayToken and TTR_GAMESERVER = GameServer,
/// then launches TTPHEngine.exe.
/// </summary>
public record LoginResponse(
    bool Success,
    string? PlayToken,
    string? GameServer,
    string Message);

/// <summary>
/// Returned to the UberDOG's WebAccountDB.lookup() callback.
///
/// DatabaseId  – the stable identifier mapped to an Astron accountId by the
///               server-side account-bridge semidbm file (i.e. the username).
/// AccountId   – always 0 here; the Python side resolves this from the local
///               account-bridge file so we never need to store Astron IDs.
/// AdminAccess – access level forwarded directly to LoginAccountFSM.
/// </summary>
public record ValidateTokenResponse(
    bool Success,
    string? DatabaseId,
    int AccountId,
    int AdminAccess,
    string? Reason);
