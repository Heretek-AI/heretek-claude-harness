// re-dotnet-cli: vendor-neutral .NET metadata reader.
//
// Subcommand surface (one JSON document on stdout per invocation):
//   check                            - print .NET runtime version
//   read-header <path>               - assembly name, version, target framework
//   list-types <path>                - every TypeDef with field/method counts
//   list-methods <path> <fqn>        - methods of one type
//   list-fields <path> <fqn>         - fields of one type
//   list-strings <path>              - #US heap strings
//   get-entry-point <path>           - <Module>::.cctor / Main
//
// NOTE: This CLI is metadata-only. C# decompilation is handled by
// the Python MCP server shelling out to `ilspycmd` (a separate
// tool). The split keeps the subprocess boundary narrow and avoids
// shipping a 5+ MB decompiler inside the metadata CLI.
//
// Errors emit a JSON {"error": "..."} document with a non-zero exit code.

using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Text.Json;
using System.Text.Json.Serialization;
using Re.Dotnet.Cli;

var subcommand = args.Length > 0 ? args[0] : "check";
var writer = new OutputWriter();

try
{
    switch (subcommand)
    {
        case "check":
            writer.Write(new
            {
                status = "OK",
                dotnet_runtime = System.Environment.Version.ToString(),
                decompiler = "(external: ilspycmd)",
            });
            break;
        case "read-header":
            RequireArg(args, 1, "read-header <path>");
            writer.Write(MetadataOps.ReadHeader(args[1]));
            break;
        case "list-types":
            RequireArg(args, 1, "list-types <path>");
            writer.Write(MetadataOps.ListTypes(args[1]));
            break;
        case "list-methods":
            RequireArg(args, 2, "list-methods <path> <fqn>");
            writer.Write(MetadataOps.ListMethods(args[1], args[2]));
            break;
        case "list-fields":
            RequireArg(args, 2, "list-fields <path> <fqn>");
            writer.Write(MetadataOps.ListFields(args[1], args[2]));
            break;
        case "list-strings":
            RequireArg(args, 1, "list-strings <path>");
            var substring = ArgOrDefault(args, 2, "");
            var limit = int.Parse(ArgOrDefault(args, 3, "500"));
            writer.Write(MetadataOps.ListStrings(args[1], substring, limit));
            break;
        case "list-ldstr":
            // A11 (v2.8.1): walk the IL stream for ldstr operands.
            // Args: <path> [substring] [limit]
            RequireArg(args, 1, "list-ldstr <path>");
            var ldstr_substring = ArgOrDefault(args, 2, "");
            var ldstr_limit = int.Parse(ArgOrDefault(args, 3, "500"));
            writer.Write(MetadataOps.ListLdstr(args[1], ldstr_substring, ldstr_limit));
            break;
        case "get-entry-point":
            RequireArg(args, 1, "get-entry-point <path>");
            writer.Write(MetadataOps.GetEntryPoint(args[1]));
            break;
        default:
            writer.WriteError($"unknown subcommand: {subcommand}");
            return 2;
    }
    return 0;
}
catch (Exception ex)
{
    writer.WriteError(ex.ToString());
    return 1;
}

static void RequireArg(string[] argv, int index, string usage)
{
    if (argv.Length <= index)
    {
        throw new ArgumentException($"missing required argument: {usage}");
    }
}

static string ArgOrDefault(string[] argv, int index, string fallback)
{
    return argv.Length > index ? argv[index] : fallback;
}

internal sealed class OutputWriter
{
    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = false,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public void Write(object payload)
    {
        Console.Out.WriteLine(JsonSerializer.Serialize(payload, Options));
    }

    public void WriteError(string message)
    {
        Console.Error.WriteLine(JsonSerializer.Serialize(new { error = message }, Options));
    }
}
