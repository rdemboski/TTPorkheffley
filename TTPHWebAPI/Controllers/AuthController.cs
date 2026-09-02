using Microsoft.AspNetCore.Mvc;
using TTPHWebAPI.Models;
using TTPHWebAPI.Services;

namespace TTPHWebAPI.Controllers;

[ApiController]
[Route("api/auth")]
public class AuthController : ControllerBase
{
    private readonly IAccountService _accounts;

    public AuthController(IAccountService accounts)
    {
        _accounts = accounts;
    }

    // -----------------------------------------------------------------------
    // POST /api/auth/register
    // Called by the launcher's registration screen.
    // -----------------------------------------------------------------------
    [HttpPost("register")]
    [ProducesResponseType(typeof(RegisterResponse), 200)]
    [ProducesResponseType(typeof(RegisterResponse), 400)]
    public async Task<IActionResult> Register([FromBody] RegisterRequest request)
    {
        var (success, message) = await _accounts.RegisterAsync(
            request.Username, request.Email, request.Password);

        return success
            ? Ok(new RegisterResponse(true, message))
            : BadRequest(new RegisterResponse(false, message));
    }

    // -----------------------------------------------------------------------
    // POST /api/auth/login
    // Called by the launcher after the user enters credentials.
    // Returns a play token and game server address on success.
    // The launcher passes these to TTPHEngine.exe via env vars:
    //   TTR_PLAYCOOKIE = PlayToken
    //   TTR_GAMESERVER = GameServer
    // -----------------------------------------------------------------------
    [HttpPost("login")]
    [ProducesResponseType(typeof(LoginResponse), 200)]
    [ProducesResponseType(typeof(LoginResponse), 401)]
    public async Task<IActionResult> Login([FromBody] LoginRequest request)
    {
        var (success, token, gameServer, message) = await _accounts.LoginAsync(
            request.Username, request.Password);

        return success
            ? Ok(new LoginResponse(true, token, gameServer, message))
            : Unauthorized(new LoginResponse(false, null, null, message));
    }

    // -----------------------------------------------------------------------
    // POST /api/auth/validate-token
    // Called internally by the UberDOG's WebAccountDB.lookup().
    // NOT intended to be exposed publicly — restrict via firewall or an
    // internal-only port in production.
    //
    // Returns:
    //   databaseId  – the account's Username, used as the stable key in the
    //                 game server's local account-bridge semidbm file.
    //   accountId   – always 0; the Python side resolves this from account-bridge.
    //   adminAccess – forwarded directly to Astron's LoginAccountFSM.
    // -----------------------------------------------------------------------
    [HttpPost("validate-token")]
    [ProducesResponseType(typeof(ValidateTokenResponse), 200)]
    [ProducesResponseType(typeof(ValidateTokenResponse), 401)]
    public async Task<IActionResult> ValidateToken([FromBody] ValidateTokenRequest request)
    {
        var result = await _accounts.ValidateTokenAsync(request.Token);

        return result.Success
            ? Ok(new ValidateTokenResponse(true, result.DatabaseId, 0, result.AdminAccess, null))
            : Unauthorized(new ValidateTokenResponse(false, null, 0, 0, result.Reason));
    }
}
