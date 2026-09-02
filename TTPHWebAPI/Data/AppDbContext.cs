using Microsoft.EntityFrameworkCore;
using TTPHWebAPI.Models;

namespace TTPHWebAPI.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<Account> Accounts => Set<Account>();
    public DbSet<PlayToken> PlayTokens => Set<PlayToken>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Account>(entity =>
        {
            entity.HasIndex(a => a.Username).IsUnique();
            entity.HasIndex(a => a.Email).IsUnique();
        });

        modelBuilder.Entity<PlayToken>(entity =>
        {
            entity.HasIndex(p => p.Token).IsUnique();
            entity.HasOne(p => p.Account)
                  .WithMany(a => a.PlayTokens)
                  .HasForeignKey(p => p.AccountId)
                  .OnDelete(DeleteBehavior.Cascade);
        });
    }
}
