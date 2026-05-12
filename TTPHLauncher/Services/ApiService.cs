using System.Net.Http;
using System.Net.Http.Json;
using TTPHLauncher.Models;

namespace TTPHLauncher.Services;

/// <summary>
/// Thin wrapper around HttpClient for all TTPHWebAPI calls.
/// Constructed once and shared across ViewModels.
/// </summary>
public class ApiService
{
    private readonly HttpClient _http;

    public ApiService()
    {
        _http = new HttpClient
        {
            BaseAddress = new Uri(LauncherConfig.Instance.ApiBaseUrl),
            Timeout = TimeSpan.FromSeconds(10),
        };
    }

    // -----------------------------------------------------------------------
    // Auth
    // -----------------------------------------------------------------------

    public async Task<LoginResponse> LoginAsync(string username, string password)
    {
        var resp = await _http.PostAsJsonAsync("/api/auth/login",
            new { username, password });

        // ReadFromJsonAsync handles both 200 and 401 bodies.
        var result = await resp.Content.ReadFromJsonAsync<LoginResponse>();
        return result ?? new LoginResponse(false, null, null, "Unexpected server response.");
    }

    public async Task<RegisterResponse> RegisterAsync(
        string username, string email, string password)
    {
        var resp = await _http.PostAsJsonAsync("/api/auth/register",
            new { username, email, password });

        var result = await resp.Content.ReadFromJsonAsync<RegisterResponse>();
        return result ?? new RegisterResponse(false, "Unexpected server response.");
    }

    // -----------------------------------------------------------------------
    // Manifest
    // -----------------------------------------------------------------------

    public async Task<string> GetManifestAsync()
    {
        return await _http.GetStringAsync("/api/manifest");
    }
}
