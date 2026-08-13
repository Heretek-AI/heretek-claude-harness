# Common native symbols reference

Quick reference for what to look for in the imports/exports of an
Android native library.

## Java_* JNI exports

Every JNI-exported function follows the pattern
``Java_<package>_<class>_<method>``. Examples:

- `Java_com_example_payment_NativeSdk_charge`
- `Java_com_example_app_MainActivity_nativeInit`

If you see these, the library is loaded by Java/Kotlin code via
`System.loadLibrary(...)`. The corresponding `loadLibrary` call in
the DEX is a great place to start dynamic hooking.

## libc / libm / libdl

The "boring" C library surface. Almost every native library imports
some of these. Look for **unusual** use:

- `dlopen` / `dlsym` / `dlclose` — runtime dynamic linking. Often
  benign (plugins), sometimes used for late-binding anti-RE tricks.
- `ptrace` — process tracing. Often a debug-detection signal.
- `execve` / `system` / `popen` — process execution. Almost always
  a red flag in a mobile app.
- `fork` — process fork. Same.
- `mprotect` / `mmap` with `PROT_EXEC` — self-modifying code, JIT.

## libc++ / stdlib

- `__cxa_atexit`, `__cxa_throw`, `_Unwind_RaiseException` — C++
  exception machinery. Standard for C++ code.
- `operator new` / `operator delete` — heap allocator. Standard.

## Anti-RE / anti-tamper

- `ptrace` (PTRACE_TRACEME) — debug-detection. Common.
- `fopen` / `stat` on `/proc/self/maps` — debugger / memory
  detection.
- `read` on `/proc/self/status` — `TracerPid` check.
- `getauxval(AT_SECURE)` — secure-execution detection.
- `sigaction` / `signal` with `SIGTRAP` / `SIGSEGV` — anti-debug
  via signal handlers.

## Crypto (libcrypto / boringssl / mbedtls)

- `AES_encrypt` / `AES_decrypt` / `AES_set_encrypt_key` — OpenSSL
  AES. Standard.
- `EC_KEY_generate_key` / `ECDH_compute_key` — ECC. Watch for
  weak curves.
- `RAND_bytes` — CSPRNG.
- `EVP_DigestInit_ex` — generic digest.
- `EVP_DecryptFinal_ex` — symmetric decrypt.
- `EVP_PKEY_verify` — signature verify.
- `BN_mod_exp` — bigint modular exponentiation. RSA / DH.

## Networking (libssl / libcurl / okhttp native)

- `SSL_CTX_new` / `SSL_read` / `SSL_write` — TLS I/O.
- `SSL_get_verify_result` — certificate validation.
- `BIO_read` / `BIO_write` — BIO abstraction.
- `curl_easy_perform` / `curl_multi_perform` — libcurl.

## File I/O

- `open` / `fopen` — standard file open.
- `read` / `write` — standard I/O.
- `unlink` / `remove` — file delete.
- `mkdir` / `chmod` — directory / permission mutation.

## Process / IPC

- `socket` / `connect` / `bind` / `listen` / `accept` — network.
- `pipe` / `fork` / `dup2` — inter-process.
- `kill` / `raise` — signals.
- `shm_open` / `mmap` — shared memory.
- `sem_wait` / `sem_post` — semaphores.
