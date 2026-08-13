// SignatureFormatter — ISignatureTypeProvider for System.Reflection.Metadata.
//
// System.Reflection.Metadata returns raw signature blobs; we need to
// format them to human-readable strings ("void(string, int)") for
// the analyst. This is a minimal, format-only implementation that
// handles the ECMA-335 types most commonly seen in real assemblies.

using System.Reflection.Metadata;

namespace Re.Dotnet.Cli;

internal sealed class SignatureFormatter : ISignatureTypeProvider<string, object?>
{
    public string GetArrayType(string elementType, ArrayShape shape) =>
        $"{elementType}[{new string(',', shape.Rank - 1)}]";

    public string GetByReferenceType(string elementType) => $"ref {elementType}";

    public string GetFunctionPointerType(MethodSignature<string> signature) =>
        $"methodptr({signature})";

    public string GetGenericInstantiation(string genericType, System.Collections.Immutable.ImmutableArray<string> typeArguments) =>
        $"{genericType}<{string.Join(", ", typeArguments)}>";

    public string GetGenericMethodParameter(object? genericContext, int index) =>
        $"!!{index}";

    public string GetGenericTypeParameter(object? genericContext, int index) =>
        $"!{index}";

    public string GetModifiedType(string modifier, string unmodifiedType, bool isRequired) =>
        $"{modifier} {unmodifiedType}";

    public string GetPinnedType(string elementType) => $"pinned {elementType}";

    public string GetPointerType(string elementType) => $"{elementType}*";

    public string GetPrimitiveType(PrimitiveTypeCode typeCode) => typeCode switch
    {
        PrimitiveTypeCode.Void => "void",
        PrimitiveTypeCode.Boolean => "bool",
        PrimitiveTypeCode.Char => "char",
        PrimitiveTypeCode.SByte => "sbyte",
        PrimitiveTypeCode.Byte => "byte",
        PrimitiveTypeCode.Int16 => "short",
        PrimitiveTypeCode.UInt16 => "ushort",
        PrimitiveTypeCode.Int32 => "int",
        PrimitiveTypeCode.UInt32 => "uint",
        PrimitiveTypeCode.Int64 => "long",
        PrimitiveTypeCode.UInt64 => "ulong",
        PrimitiveTypeCode.Single => "float",
        PrimitiveTypeCode.Double => "double",
        PrimitiveTypeCode.IntPtr => "nint",
        PrimitiveTypeCode.UIntPtr => "nuint",
        PrimitiveTypeCode.Object => "object",
        PrimitiveTypeCode.String => "string",
        PrimitiveTypeCode.TypedReference => "typedref",
        _ => typeCode.ToString(),
    };

    public string GetSZArrayType(string elementType) => $"{elementType}[]";

    public string GetTypeFromDefinition(MetadataReader reader, TypeDefinitionHandle handle, byte rawTypeKind) =>
        GetFullName(reader, handle);

    public string GetTypeFromReference(MetadataReader reader, TypeReferenceHandle handle, byte rawTypeKind) =>
        GetFullName(reader, handle);

    public string GetTypeFromSpecification(MetadataReader reader, object? genericContext, TypeSpecificationHandle handle, byte rawTypeKind) =>
        handle.ToString();

    private static string GetFullName(MetadataReader reader, TypeDefinitionHandle handle)
    {
        var t = reader.GetTypeDefinition(handle);
        var name = reader.GetString(t.Name);
        var ns = reader.GetString(t.Namespace);
        return string.IsNullOrEmpty(ns) ? name : $"{ns}.{name}";
    }

    private static string GetFullName(MetadataReader reader, TypeReferenceHandle handle)
    {
        var t = reader.GetTypeReference(handle);
        var name = reader.GetString(t.Name);
        var ns = reader.GetString(t.Namespace);
        return string.IsNullOrEmpty(ns) ? name : $"{ns}.{name}";
    }
}
