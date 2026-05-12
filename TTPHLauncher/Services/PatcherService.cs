using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using TTPHLauncher.Models;

namespace TTPHLauncher.Services;

/// <summary>
/// Parses the game manifest and keeps local phase files up-to-date by
/// downloading any file whose size or MD5 doesn't match the manifest.
///
/// Manifest format (text/plain, served by TTPHWebAPI GET /api/manifest):
///
///   REQUIRED_INSTALL_FILES=phase_3.mf:3 phase_3.5.mf:3 ...
///   FILE_phase_3.mf.current=1.0.0
///   FILE_phase_3.mf.1.0.0=&lt;bytesize&gt; &lt;md5hex&gt;
///   ...
///
/// Files are downloaded from: {CdnBaseUrl}/{filename}.{version}
/// e.g. http://cdn.example.com/files/phase_3.mf.1.0.0
/// </summary>
public class PatcherService
{
    // Built on first use so we don't crash when CdnBaseUrl is empty at startup.
    private HttpClient? _cdn;

    private HttpClient Cdn
    {
        get
        {
            if (_cdn is not null) return _cdn;

            var url = LauncherConfig.Instance.CdnBaseUrl.TrimEnd('/') + "/";
            if (!Uri.TryCreate(url, UriKind.Absolute, out var uri))
                throw new InvalidOperationException(
                    $"CdnBaseUrl '{LauncherConfig.Instance.CdnBaseUrl}' is not a valid URL. " +
                    "Set it in launcher.json (e.g. \"http://127.0.0.1:8080/files\").");

            _cdn = new HttpClient { BaseAddress = uri, Timeout = TimeSpan.FromMinutes(30) };
            return _cdn;
        }
    }

    public PatcherService() { }

    // -----------------------------------------------------------------------
    // Manifest parsing
    // -----------------------------------------------------------------------

    public List<PhaseFileInfo> ParseManifest(string manifestText)
    {
        // Build a key=value dictionary, skipping comments and blank lines.
        var kvp = manifestText
            .Split('\n')
            .Select(l => l.Trim())
            .Where(l => l.Length > 0 && !l.StartsWith('#') && l.Contains('='))
            .Select(l =>
            {
                var idx = l.IndexOf('=');
                return (Key: l[..idx], Value: l[(idx + 1)..]);
            })
            .ToDictionary(t => t.Key, t => t.Value);

        if (!kvp.TryGetValue("REQUIRED_INSTALL_FILES", out var fileList))
            return [];

        var files = new List<PhaseFileInfo>();
        foreach (var entry in fileList.Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
            var filename = entry.Split(':')[0]; // strip the flag suffix

            if (!kvp.TryGetValue($"FILE_{filename}.current", out var version))
                continue;
            if (!kvp.TryGetValue($"FILE_{filename}.{version}", out var details))
                continue;

            var parts = details.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 2) continue;

            if (!long.TryParse(parts[0], out var size) || size == 0)
                continue; // skip placeholder 0-byte entries in the example manifest

            files.Add(new PhaseFileInfo
            {
                Filename = filename,
                Version = version,
                ExpectedSize = size,
                ExpectedMd5 = parts[1].ToLowerInvariant(),
            });
        }

        return files;
    }

    // -----------------------------------------------------------------------
    // File integrity
    // -----------------------------------------------------------------------

    /// <summary>
    /// Returns true if the local copy of the file matches the manifest exactly.
    /// </summary>
    public bool IsFileUpToDate(PhaseFileInfo file)
    {
        var path = Path.Combine(LauncherConfig.Instance.ResolvedGameDirectory, file.Filename);
        if (!File.Exists(path)) return false;

        var info = new FileInfo(path);
        if (info.Length != file.ExpectedSize) return false;

        using var md5 = MD5.Create();
        using var stream = File.OpenRead(path);
        var hash = md5.ComputeHash(stream);
        var hex = Convert.ToHexString(hash).ToLowerInvariant();
        return hex == file.ExpectedMd5;
    }

    // -----------------------------------------------------------------------
    // Download
    // -----------------------------------------------------------------------

    /// <summary>
    /// Downloads a phase file from the CDN into the game directory.
    /// Reports (bytesDownloaded, totalBytes) via <paramref name="progress"/>.
    /// Writes to a .tmp file first to avoid leaving a corrupt file on error.
    /// </summary>
    public async Task DownloadFileAsync(
        PhaseFileInfo file,
        IProgress<(long Downloaded, long Total)> progress,
        CancellationToken ct = default)
    {
        var gameDir = LauncherConfig.Instance.ResolvedGameDirectory;
        Directory.CreateDirectory(gameDir);

        var localPath = Path.Combine(gameDir, file.Filename);
        var tempPath = localPath + ".tmp";

        using var resp = await Cdn.GetAsync(
            file.CdnPath, HttpCompletionOption.ResponseHeadersRead, ct);
        resp.EnsureSuccessStatusCode();

        var total = resp.Content.Headers.ContentLength ?? file.ExpectedSize;
        long downloaded = 0;

        await using var remote = await resp.Content.ReadAsStreamAsync(ct);
        await using var local = File.Create(tempPath);

        var buffer = new byte[81_920]; // 80 KB chunks
        int read;
        while ((read = await remote.ReadAsync(buffer, ct)) > 0)
        {
            await local.WriteAsync(buffer.AsMemory(0, read), ct);
            downloaded += read;
            progress.Report((downloaded, total));
        }

        local.Close();

        // Atomic-ish swap
        if (File.Exists(localPath)) File.Delete(localPath);
        File.Move(tempPath, localPath);
    }
}
