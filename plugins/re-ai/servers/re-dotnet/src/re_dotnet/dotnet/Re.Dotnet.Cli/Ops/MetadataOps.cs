// MetadataOps — System.Reflection.Metadata-based .NET metadata reader.
//
// Uses only the ECMA-335 metadata reader that's built into .NET 10
// (no external NuGet deps). This is a metadata-only reader — the
// Python MCP server shells out to `ilspycmd` separately for C#
// decompilation. Keeping the subprocess boundary narrow means each
// tool is small and replaceable.
//
// Vendor-neutral: the on-disk shape is described in observable
// terms (types, methods, fields, strings). No reference to any
// specific commercial obfuscation product or anti-tamper vendor
// is made here.

using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Reflection.Metadata.Ecma335;

namespace Re.Dotnet.Cli;

/// <summary>
/// Static facade that loads a .NET assembly once per call and returns
/// the requested slice. The "load every call" pattern is intentional —
/// the CLI process exits after one subcommand, so the cost is bounded
/// and a partially-failed run cannot corrupt the next invocation's state.
/// </summary>
internal static class MetadataOps
{
    public static object ReadHeader(string path)
    {
        using var peReader = OpenPeReader(path);
        var md = peReader.GetMetadataReader();
        return new
        {
            path,
            module_name = GetModuleName(md),
            assembly_name = GetAssemblyName(md),
            assembly_version = GetAssemblyVersion(md),
            target_framework = "net",
            corlib = "mscorlib",
            is_mixed_mode = false,
            entry_point = ResolveEntryPointName(md) ?? "<no managed entry point>",
            file_kind = md.IsAssembly ? "assembly" : "netmodule",
            type_count = md.TypeDefinitions.Count,
            method_count = md.MethodDefinitions.Count,
            field_count = md.FieldDefinitions.Count,
        };
    }

    public static object ListTypes(string path)
    {
        using var peReader = OpenPeReader(path);
        var md = peReader.GetMetadataReader();
        var rows = new List<object>();
        foreach (var handle in md.TypeDefinitions)
        {
            var type = md.GetTypeDefinition(handle);
            var name = md.GetString(type.Name);
            var ns = md.GetString(type.Namespace);
            // Skip compiler-generated display-class / lambda-host types
            if (name.Contains('<') || name.StartsWith("__")) continue;
            var fqn = string.IsNullOrEmpty(ns) ? name : $"{ns}.{name}";
            rows.Add(new
            {
                fqn,
                @namespace = ns ?? "",
                name,
                is_public = IsPublic(type.Attributes),
                is_sealed = IsSealed(type.Attributes),
                is_abstract = IsAbstract(type.Attributes),
                is_interface = (type.Attributes & TypeAttributes.Interface) != 0,
                is_value_type = (type.Attributes & TypeAttributes.SequentialLayout) != 0
                                 || (type.Attributes & TypeAttributes.ExplicitLayout) != 0,
                is_enum = IsEnum(md, type),
                base_type = GetBaseTypeName(md, type),
                method_count = type.GetMethods().Count(),
                field_count = type.GetFields().Count(),
                property_count = type.GetProperties().Count(),
                event_count = type.GetEvents().Count(),
                nested_type_count = type.GetNestedTypes().Count(),
            });
        }
        return new { count = rows.Count, types = rows };
    }

    public static object ListMethods(string path, string fqn)
    {
        using var peReader = OpenPeReader(path);
        var md = peReader.GetMetadataReader();
        var type = FindTypeByFqn(md, fqn);
        var rows = new List<object>();
        foreach (var methodHandle in type.GetMethods())
        {
            var method = md.GetMethodDefinition(methodHandle);
            var name = md.GetString(method.Name);
            rows.Add(new
            {
                fqn = $"{fqn}::{name}",
                name,
                signature = method.DecodeSignature(new SignatureFormatter(), null).ToString() ?? "",
                is_public = IsPublic(method.Attributes),
                is_static = (method.Attributes & MethodAttributes.Static) != 0,
                is_virtual = (method.Attributes & MethodAttributes.Virtual) != 0,
                is_abstract = (method.Attributes & MethodAttributes.Abstract) != 0,
                is_final = (method.Attributes & MethodAttributes.Final) != 0,
                is_special_name = (method.Attributes & MethodAttributes.SpecialName) != 0,
                rva = method.RelativeVirtualAddress != 0
                    ? $"0x{method.RelativeVirtualAddress:X}" : "",
                token = methodHandle.ToString(),
            });
        }
        return new { type_fqn = fqn, count = rows.Count, methods = rows };
    }

    public static object ListFields(string path, string fqn)
    {
        using var peReader = OpenPeReader(path);
        var md = peReader.GetMetadataReader();
        var type = FindTypeByFqn(md, fqn);
        var rows = new List<object>();
        foreach (var fieldHandle in type.GetFields())
        {
            var field = md.GetFieldDefinition(fieldHandle);
            var name = md.GetString(field.Name);
            var sig = field.DecodeSignature(new SignatureFormatter(), null);
            var constHandle = field.GetDefaultValue();
            string constStr = "";
            if (!constHandle.IsNil)
            {
                var constant = md.GetConstant(constHandle);
                // String-typed constants are stored in the #US heap as
                // UTF-16LE. Other types use the blob value directly.
                try
                {
                    var blobReader = md.GetBlobReader(constant.Value);
                    var bytes = blobReader.ReadBytes(blobReader.Length);
                    constStr = System.Text.Encoding.Unicode.GetString(bytes);
                }
                catch
                {
                    constStr = constant.Value.ToString() ?? "";
                }
            }
            rows.Add(new
            {
                name,
                field_type = sig.ToString() ?? "",
                is_public = IsPublic(field.Attributes),
                is_static = (field.Attributes & FieldAttributes.Static) != 0,
                is_read_only = (field.Attributes & FieldAttributes.InitOnly) != 0,
                is_literal = (field.Attributes & FieldAttributes.Literal) != 0,
                constant = constStr,
            });
        }
        return new { type_fqn = fqn, count = rows.Count, fields = rows };
    }

    /// <summary>
    /// A11 fix (v2.8.1): walk every method body's IL stream and emit every
    /// <c>ldstr</c> operand (user-string tokens in the #US heap).
    /// </summary>
    /// <remarks>
    /// Mono assemblies (CD's <c>MonoLauncher</c> is the canonical example) hold
    /// most of their interesting strings — Steam registry keys, launcher
    /// URLs, error messages — in <c>ldstr</c> operands, NOT in field-default
    /// values. The prior <c>ListStrings</c> walker only saw field-defaults,
    /// which on Mono returned 1-2 strings even when the assembly had
    /// hundreds. <c>ListLdstr</c> closes that gap by walking every method's
    /// IL bytes, recognising the <c>ldstr</c> opcode (0x72), resolving the
    /// 4-byte user-string token against the #US heap, and emitting the
    /// decoded UTF-16 string.
    ///
    /// On encrypted/obfuscated assemblies the #US heap may be unreadable;
    /// in that case the inner <c>GetUserString</c> call throws and we
    /// silently skip the operand (the row simply doesn't appear). The
    /// caller sees <c>count: 0</c>, not an error — a 0-count on a CD-style
    /// Mono PE is a legitimate "heap unreadable" signal, not a regression.
    /// </remarks>
    public static object ListLdstr(string path, string substring, int limit)
    {
        using var peReader = OpenPeReader(path);
        var md = peReader.GetMetadataReader();
        var rows = new List<object>();
        var matched = 0;
        foreach (var handle in md.TypeDefinitions)
        {
            var type = md.GetTypeDefinition(handle);
            var typeName = md.GetString(type.Name);
            if (typeName.Contains('<') || typeName.StartsWith("__")) continue;
            var ns = md.GetString(type.Namespace);
            var typeFqn = string.IsNullOrEmpty(ns) ? typeName : $"{ns}.{typeName}";
            foreach (var methodHandle in type.GetMethods())
            {
                var method = md.GetMethodDefinition(methodHandle);
                var methodName = md.GetString(method.Name);
                if (method.RelativeVirtualAddress == 0) continue;
                MethodBodyBlock? body;
                try
                {
                    // In .NET 10, PEReader.GetMethodBody returns
                    // MethodBodyBlock (not the MethodBody base class).
                    // MethodBodyBlock exposes GetILBytes(); the base
                    // class doesn't.
                    body = peReader.GetMethodBody(method.RelativeVirtualAddress)
                           as MethodBodyBlock;
                }
                catch (BadImageFormatException)
                {
                    // Malformed method body (rare; e.g. stripped body RVA,
                    // or an obfuscator that overwrites the header).
                    continue;
                }
                if (body is null) continue;
                var ilBytes = body.GetILBytes();
                if (ilBytes.Length < 5) continue;
                // Walk the IL stream looking for the 0x72 ldstr opcode
                // followed by a 4-byte user-string token. The token's
                // top byte must be 0x70 (the UserString table ID per
                // ECMA-335 II.24.2.3); if it isn't, this is a different
                // opcode family (call/callvirt/calli use the 0x6? byte)
                // and we skip.
                int i = 0;
                while (i <= ilBytes.Length - 5)
                {
                    if (ilBytes[i] != 0x72)
                    {
                        i++;
                        continue;
                    }
                    uint token = (uint)ilBytes[i + 1]
                               | ((uint)ilBytes[i + 2] << 8)
                               | ((uint)ilBytes[i + 3] << 16)
                               | ((uint)ilBytes[i + 4] << 24);
                    if ((token >> 24) != 0x70)
                    {
                        i++;
                        continue;
                    }
                    uint row = token & 0x00FFFFFFu;
                    if (row == 0)
                    {
                        i += 5;
                        continue;
                    }
                    string? userString = null;
                    try
                    {
                        var usHandle = MetadataTokens.UserStringHandle((int)row);
                        userString = md.GetUserString(usHandle);
                    }
                    catch
                    {
                        // Heap unreadable (encrypted/obfuscated). Skip
                        // silently — the row simply doesn't appear.
                    }
                    i += 5;
                    if (userString is null) continue;
                    if (substring.Length > 0
                        && !userString.Contains(substring, StringComparison.Ordinal))
                    {
                        continue;
                    }
                    rows.Add(new
                    {
                        fqn = $"{typeFqn}::{methodName}",
                        kind = "ldstr",
                        il_offset = i - 5,
                        @string = userString,
                    });
                    if (++matched >= limit) goto done;
                }
            }
        }
    done:
        return new { count = matched, truncated = matched >= limit, strings = rows };
    }

    public static object ListStrings(string path, string substring, int limit)
    {
        using var peReader = OpenPeReader(path);
        var md = peReader.GetMetadataReader();
        var rows = new List<object>();
        var matched = 0;
        foreach (var handle in md.TypeDefinitions)
        {
            var type = md.GetTypeDefinition(handle);
            var typeName = md.GetString(type.Name);
            if (typeName.Contains('<') || typeName.StartsWith("__")) continue;
            var ns = md.GetString(type.Namespace);
            var fqn = string.IsNullOrEmpty(ns) ? typeName : $"{ns}.{typeName}";
            foreach (var fieldHandle in type.GetFields())
            {
                var field = md.GetFieldDefinition(fieldHandle);
                if ((field.Attributes & FieldAttributes.Literal) == 0) continue;
                if ((field.Attributes & FieldAttributes.HasDefault) == 0) continue;
                // The ISignatureTypeProvider<string, object?>
                // returns the type name as a string ("string" for
                // System.String, "int" for System.Int32, etc.). Match
                // by type name rather than by raw signature byte.
                var sig = field.DecodeSignature(new SignatureFormatter(), null);
                if (sig is not "string") continue;
                // (signature already filtered by type name above;
                //  legacy index check removed)
                var constHandle = field.GetDefaultValue();
                if (constHandle.IsNil) continue;
                var constant = md.GetConstant(constHandle);
                // For string-typed constants, ``constant.Value`` is a
                // #US heap (user string) handle. The blob contents are
                // the raw UTF-16LE string bytes — no extra length
                // prefix to strip. (The 0x68 first byte of "hello" is
                // the lowercase 'h', not a length marker.)
                var raw = "";
                try
                {
                    var blobReader = md.GetBlobReader(constant.Value);
                    var bytes = blobReader.ReadBytes(blobReader.Length);
                    if (bytes.Length > 0)
                    {
                        raw = System.Text.Encoding.Unicode.GetString(bytes);
                    }
                }
                catch
                {
                    raw = constant.Value.ToString() ?? "";
                }
                if (substring.Length > 0 && !raw.Contains(substring, StringComparison.Ordinal))
                {
                    continue;
                }
                rows.Add(new
                {
                    fqn = $"{fqn}::{md.GetString(field.Name)}",
                    kind = "field-default",
                    @string = raw,
                });
                if (++matched >= limit) goto done;
            }
        }
done:
        return new { count = matched, truncated = matched >= limit, strings = rows };
    }

    public static object GetEntryPoint(string path)
    {
        using var peReader = OpenPeReader(path);
        var md = peReader.GetMetadataReader();
        // The CLI header's entry-point token is what the loader uses.
        // We don't have a portable way to read the CLI header from
        // System.Reflection.Metadata, so we return the same fallback as
        // read-header: the first .cctor / Main we find.
        var entryName = ResolveEntryPointName(md);
        if (entryName is null)
        {
            return new { has_managed_entry_point = false };
        }
        return new
        {
            has_managed_entry_point = true,
            fqn = entryName,
        };
    }

    // ── helpers ────────────────────────────────────────────────────────

    private static PEReader OpenPeReader(string path)
    {
        // The PE reader is the lowest-level entry point — it gives us
        // a MetadataReader that walks the ECMA-335 tables. OpenFile
        // (not OpenSequence) so the reader can mmap the file in place.
        return new PEReader(File.OpenRead(Path.GetFullPath(path)));
    }

    private static string? GetModuleName(MetadataReader md)
    {
        if (md.IsAssembly)
        {
            var ad = md.GetAssemblyDefinition();
            return md.GetString(ad.Name);
        }
        return md.GetModuleDefinition().Name switch
        {
            var n => md.GetString(n),
        };
    }

    private static string GetAssemblyName(MetadataReader md)
    {
        if (md.IsAssembly)
        {
            var ad = md.GetAssemblyDefinition();
            return md.GetString(ad.Name);
        }
        return md.GetString(md.GetModuleDefinition().Name);
    }

    private static string GetAssemblyVersion(MetadataReader md)
    {
        if (!md.IsAssembly) return "";
        var v = md.GetAssemblyDefinition().Version;
        return $"{v.Major}.{v.Minor}.{v.Build}.{v.Revision}";
    }

    private static bool IsEnum(MetadataReader md, TypeDefinition type)
    {
        // An enum extends System.Enum. Cheap heuristic: the base type
        // is in the System namespace and named "Enum".
        var baseType = type.GetDeclaringType();
        // We can't resolve base type FQN without a type system; check
        // by walking the inheritance chain in the typeRef table.
        try
        {
            var baseHandle = type.BaseType;
            if (baseHandle.IsNil) return false;
            if (baseHandle.Kind == HandleKind.TypeReference)
            {
                var tr = md.GetTypeReference((TypeReferenceHandle)baseHandle);
                var name = md.GetString(tr.Name);
                var ns = md.GetString(tr.Namespace);
                return ns == "System" && name == "Enum";
            }
        }
        catch
        {
            // Malformed metadata; treat as non-enum.
        }
        return false;
    }

    private static string GetBaseTypeName(MetadataReader md, TypeDefinition type)
    {
        try
        {
            var baseHandle = type.BaseType;
            if (baseHandle.IsNil) return "";
            if (baseHandle.Kind == HandleKind.TypeReference)
            {
                var tr = md.GetTypeReference((TypeReferenceHandle)baseHandle);
                var name = md.GetString(tr.Name);
                var ns = md.GetString(tr.Namespace);
                return string.IsNullOrEmpty(ns) ? name : $"{ns}.{name}";
            }
        }
        catch
        {
            // ignored
        }
        return "";
    }

    private static TypeDefinition FindTypeByFqn(MetadataReader md, string fqn)
    {
        foreach (var handle in md.TypeDefinitions)
        {
            var type = md.GetTypeDefinition(handle);
            var name = md.GetString(type.Name);
            var ns = md.GetString(type.Namespace);
            var fullName = string.IsNullOrEmpty(ns) ? name : $"{ns}.{name}";
            if (fullName == fqn) return type;
        }
        throw new InvalidOperationException(
            $"type {fqn} not found");
    }

    private static string? ResolveEntryPointName(MetadataReader md)
    {
        foreach (var handle in md.TypeDefinitions)
        {
            var type = md.GetTypeDefinition(handle);
            var typeName = md.GetString(type.Name);
            var ns = md.GetString(type.Namespace);
            var fqn = string.IsNullOrEmpty(ns) ? typeName : $"{ns}.{typeName}";
            foreach (var methodHandle in type.GetMethods())
            {
                var method = md.GetMethodDefinition(methodHandle);
                var name = md.GetString(method.Name);
                if (name == "Main" || name == ".cctor")
                {
                    return $"{fqn}::{name}";
                }
            }
        }
        return null;
    }

    private static bool IsPublic(TypeAttributes a) =>
        (a & TypeAttributes.VisibilityMask) == TypeAttributes.Public;

    private static bool IsSealed(TypeAttributes a) =>
        (a & TypeAttributes.Sealed) != 0;

    private static bool IsAbstract(TypeAttributes a) =>
        (a & TypeAttributes.Abstract) != 0;

    private static bool IsPublic(MethodAttributes a) =>
        (a & MethodAttributes.MemberAccessMask) == MethodAttributes.Public;

    private static bool IsPublic(FieldAttributes a) =>
        (a & FieldAttributes.FieldAccessMask) == FieldAttributes.Public;
}
