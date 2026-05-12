using Microsoft.EntityFrameworkCore;
using TTPHWebAPI.Data;
using TTPHWebAPI.Services;

var builder = WebApplication.CreateBuilder(args);

// -------------------------------------------------------------------------
// Services
// -------------------------------------------------------------------------
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        // Use camelCase for all JSON output so the Python UberDOG's
        // result.get('databaseId') / result.get('adminAccess') calls match.
        options.JsonSerializerOptions.PropertyNamingPolicy =
            System.Text.Json.JsonNamingPolicy.CamelCase;
    });
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new() { Title = "TTPH Web API", Version = "v1" });
});

// EF Core — provider is selected by the "DbProvider" config key.
// Locally this defaults to "Sqlite" via appsettings.json.
// On Azure App Service, set DbProvider=SqlServer and supply the
// connection string via Configuration > Connection strings (key: DefaultConnection).
var dbProvider = builder.Configuration["DbProvider"] ?? "Sqlite";
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection")
    ?? "Data Source=ttph.db";

builder.Services.AddDbContext<AppDbContext>(options =>
{
    if (dbProvider == "SqlServer")
        options.UseSqlServer(connectionString, sql =>
            sql.EnableRetryOnFailure()); // transient fault handling for Azure SQL
    else
        options.UseSqlite(connectionString);
});

builder.Services.AddScoped<IAccountService, AccountService>();

// -------------------------------------------------------------------------
// App pipeline
// -------------------------------------------------------------------------
var app = builder.Build();

// Apply any pending migrations on startup (creates tables on first run).
// Safe to call on every startup — EF is a no-op when the schema is current.
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.Migrate();
}

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.MapControllers();
app.Run();
