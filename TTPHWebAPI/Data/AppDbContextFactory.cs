using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace TTPHWebAPI.Data;

/// <summary>
/// Used by EF Core CLI tooling (dotnet ef migrations add / dotnet ef database update)
/// to create an AppDbContext at design time, targeting SQL Server so that generated
/// migrations are compatible with the Azure SQL production database.
///
/// This class is never instantiated at runtime — it is only picked up by the EF tools.
/// </summary>
public class AppDbContextFactory : IDesignTimeDbContextFactory<AppDbContext>
{
    public AppDbContext CreateDbContext(string[] args)
    {
        var optionsBuilder = new DbContextOptionsBuilder<AppDbContext>();

        // Point at a real Azure SQL connection string for migration generation,
        // or use LocalDB if you have SQL Server installed locally.
        // The actual value here only matters for tooling — it is not used at runtime.
        var connectionString =
            Environment.GetEnvironmentVariable("TTPH_DESIGN_TIME_CONNECTION")
            ?? "Server=(localdb)\\mssqllocaldb;Database=ttph_dev;Trusted_Connection=True;";

        optionsBuilder.UseSqlServer(connectionString);
        return new AppDbContext(optionsBuilder.Options);
    }
}
