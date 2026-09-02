using Microsoft.AspNetCore.Mvc;

namespace TTPHWebAPI.Controllers;

/// <summary>
/// Serves the patch manifest consumed by the launcher's QuickLauncher patcher.
///
/// Manifest format (parsed by QuickLauncher.downloadLauncherFileDbDone):
///
///   REQUIRED_INSTALL_FILES=phase_3.mf:3 phase_3.5.mf:3 ...
///   FILE_phase_3.mf.current=1.0.0
///   FILE_phase_3.mf.1.0.0=&lt;bytesize&gt; &lt;md5hex&gt;
///   ...
///
/// The flag after the colon (:3) is a 3-bit mask:
///   bit 0 = extract into VFS, bit 1 = required, bit 2 = optional download
///   Value 3 (extract + required) is correct for all phase files.
///
/// Phase files are hosted on a CDN/file server — this endpoint just describes
/// what to download, not serves the files themselves.
/// </summary>
[ApiController]
[Route("api")]
public class ManifestController : ControllerBase
{
    private readonly IConfiguration _config;
    private readonly IWebHostEnvironment _env;

    public ManifestController(IConfiguration config, IWebHostEnvironment env)
    {
        _config = config;
        _env = env;
    }

    // -----------------------------------------------------------------------
    // GET /api/manifest
    // Returns the text manifest consumed by the launcher patcher.
    // Serve from a static file placed at <WebRoot>/manifest.txt (wwwroot/).
    // -----------------------------------------------------------------------
    [HttpGet("manifest")]
    [Produces("text/plain")]
    public IActionResult GetManifest()
    {
        var manifestPath = Path.Combine(_env.WebRootPath, "manifest.txt");
        if (!System.IO.File.Exists(manifestPath))
        {
            return NotFound("manifest.txt not found. Place it in the wwwroot folder.");
        }

        return PhysicalFile(manifestPath, "text/plain");
    }

    // -----------------------------------------------------------------------
    // GET /api/version
    // Returns the current server version string.
    // The launcher can display this and compare against the locally cached
    // version to decide whether a re-patch is needed.
    // -----------------------------------------------------------------------
    [HttpGet("version")]
    public IActionResult GetVersion()
    {
        return Ok(new
        {
            version = _config["ServerVersion"] ?? "no_version_set"
        });
    }
}
