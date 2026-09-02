using System.Text.Json.Serialization;

namespace TTPHLauncher.Models;

// Mirrors the DTOs in TTPHWebAPI — kept in sync manually (or move to a shared project later).

public record LoginResponse(
    bool Success,
    string? PlayToken,
    string? GameServer,
    string Message);

public record RegisterResponse(
    bool Success,
    string Message);

/// <summary>Describes one phase file entry parsed from the manifest.</summary>
public class PhaseFileInfo
{
    public string Filename { get; init; } = "";
    public string Version { get; init; } = "";
    public long ExpectedSize { get; init; }
    public string ExpectedMd5 { get; init; } = "";

    [JsonIgnore]
    public string CdnPath => Filename; // relative URL segment on the CDN (Azure blobs are plain phase_X.mf)
}
