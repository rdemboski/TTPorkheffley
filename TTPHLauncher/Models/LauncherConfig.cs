using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace TTPHLauncher.Models;

/// <summary>
/// Loaded once at startup from launcher.json next to the exe.
/// Operators edit this file when deploying to point at real servers.
/// </summary>
public class LauncherConfig
{
    // Lazy singleton — load once, share everywhere.
    private static LauncherConfig? _instance;
    public static LauncherConfig Instance => _instance ??= Load();

    /// <summary>Base URL of TTPHWebAPI (login / register / manifest).</summary>
    public string ApiBaseUrl { get; set; } = "http://127.0.0.1:5000";

    /// <summary>
    /// Base URL of the CDN/file server hosting phase_X.mf files.
    /// Files are requested as: {CdnBaseUrl}/{filename}
    /// e.g. https://ttphcdn.blob.core.windows.net/resources/phase_3.mf
    /// Set to an empty string to skip the patcher entirely (dev mode).
    /// </summary>
    public string CdnBaseUrl { get; set; } = "";

    /// <summary>
    /// Directory where phase_*.mf files live on disk (absolute or relative to launcher).
    /// If relative, it's resolved against the launcher exe's directory.
    /// </summary>
    public string GameDirectory { get; set; } = ".";

    /// <summary>Executable to launch when the Play button is clicked.</summary>
    public string GameExecutable { get; set; } = "TTPHEngine.exe";

    /// <summary>
    /// If set, overrides the game server address returned by the API after login.
    /// Useful for running the server locally without changing the shared Azure setting.
    /// Leave empty in the distributed launcher.json.
    /// e.g. "127.0.0.1:7198"
    /// </summary>
    public string GameServerOverride { get; set; } = "";

    // -----------------------------------------------------------------------
    [JsonIgnore]
    public string ResolvedGameDirectory =>
        Path.IsPathRooted(GameDirectory)
            ? GameDirectory
            : Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, GameDirectory));

    [JsonIgnore]
    public bool PatcherEnabled => !string.IsNullOrWhiteSpace(CdnBaseUrl);

    // -----------------------------------------------------------------------
    private static readonly JsonSerializerOptions _opts = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    private static LauncherConfig Load()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "launcher.json");
        if (!File.Exists(path))
            return new LauncherConfig();

        try
        {
            var json = File.ReadAllText(path);
            return JsonSerializer.Deserialize<LauncherConfig>(json, _opts)
                   ?? new LauncherConfig();
        }
        catch
        {
            return new LauncherConfig();
        }
    }
}
