cmake_minimum_required(VERSION 3.16)
project(vtil-cli CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Threads::Threads imported target — required by the
# target_link_libraries call below (VTIL uses pthread internally).
find_package(Threads REQUIRED)

# v2.9.2 (Gap 13 fix): wire in real VTIL-Core.
#
# Vendored under third party/VTIL-Core/ (BSD-3-Clause, see
# docs/THIRD-PARTY-LICENSES.md#vtil-core). The build pulls
# capstone + keystone via VTIL-Core's own FetchContent at
# configure time.
#
# The RE-AI vendor-leakage test allows this dir via
# tests/test_no_vendor_leakage.py (mirror the data/ksy/ pattern).
#
# The v2.9.2 main.cpp uses ONLY the disassembler umbrella
# (vtil/amd64). The full vtil::arch::translate + vtil::routine
# round-trip is deferred to v2.9.3 (it requires additional
# include-path work for the VTIL-Common assembler headers, which
# have their own C++20-narrowing incompatibilities that need a
# vtil-cli precompiled-headers workaround).
#
# Build requirements (see install.sh:566-594):
#   - cmake >= 3.16
#   - C++20 compiler (clang 12+ or gcc 10+; clang preferred
#     because the keystone LLVM subset has C++17-std::binary_function
#     issues on gcc 16)
#   - pthread
#   - network access at configure time (FetchContent pulls
#     capstone + keystone)
set(RE_VTIL_VENDORED ON CACHE BOOL "Build against vendored VTIL-Core")
if(RE_VTIL_VENDORED)
    set(VTIL_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    set(VTIL_UNITY_BUILD OFF CACHE BOOL "" FORCE)
    # Keystone is GPLv2 — build it as a shared lib so the
    # final vtil-cli binary doesn't statically embed its objects
    # (mitigates the GPLv2 distribution concern).
    set(Keystone_BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)
    # Keystone's vendored LLVM subset (STLExtras.h) uses `intptr_t`
    # without including <cstdint>. Modern libc++/libstdc++ no longer
    # transitively expose it, so clang 22 / gcc 16 fail with
    # "unknown type name 'intptr_t'". Inject -include cstdint
    # GLOBALLY before add_subdirectory so it covers the keystone
    # subproject's C++ translation units. The same flag is also
    # set per-target on vtil-cli below as a safety net.
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -include cstdint")
    add_subdirectory("third party/VTIL-Core" EXCLUDE_FROM_ALL)
else()
    find_package(VTIL CONFIG REQUIRED)
endif()

add_executable(vtil-cli src/main.cpp)

# v2.9.2 MVP: link only the libraries the vtil::amd64::disasm
# umbrella needs. The full v2.9.3 link list will add the optimizer
# (VTIL-Compiler) when the translate-to-IL round-trip lands.
target_link_libraries(vtil-cli
    PRIVATE
        VTIL-Common
        VTIL-Architecture
        VTIL-SymEx
        VTIL-Compiler
        capstone-static
        keystone
        Threads::Threads
        dl
)

# VTIL-Core uses C++20 features (std::unary_function / binary_function
# in keystone's LLVM subset) that GCC 16 deprecated-removed. The
# -include cstdint preinclude fixes the missing-intptr_t errors
# in keystone's STLExtras.h. The Wno-* flags silence VTIL's own
# deprecation warnings (they're harmless — the upstream is on
# master with no tagged release).
target_compile_options(vtil-cli PRIVATE
    -include cstdint
    $<$<CXX_COMPILER_ID:GNU>:-Wno-narrowing -Wno-format-security
                               -Wno-unused-value -Wno-uninitialized
                               -Wno-parentheses -Wno-attributes
                               -Wno-multichar>
)

# The install location: install.sh copies build/vtil-cli to
# servers/re-vtil/bin/vtil-cli (the runner.py fallback chain
# looks for the helper there).  Leaving the binary at the
# default ${CMAKE_BINARY_DIR}/vtil-cli is what install.sh
# expects (see install.sh:609 `cp "${VTIL_PROJ}/build/vtil-cli"`).
# No RUNTIME_OUTPUT_DIRECTORY override here.
