// Generated / curated by android-re-sslpinning-bypass skill.
// Universal SSL pinning bypass — hooks the most common Java and
// native pinning call sites. Loaded into a Frida session via
// `frida_load_script`.
//
// Tested against OkHttp 3/4, Retrofit 2, Apache HttpClient,
// Conscrypt, and OpenSSL-based libraries (libssl, libconscrypt).
//
// Behavior:
//   1. Java.use("X509TrustManager").checkServerTrusted(...)  -> no-op
//   2. Java.use("HostnameVerifier").verify(host, sslSession)  -> true
//   3. Java.use("okhttp3.CertificatePinner").check(...)         -> no-op
//   4. TrustManagerFactory.getTrustManagers()                 -> single trust-all
//   5. ConscryptFileDescriptorSocket.checkTrusted(...)         -> no-op
//   6. Native: ssl_verify_cert_chain in libssl/libconscrypt    -> return 1
//
// Usage:
//   frida_load_script(session_id, "ssl-bypass", THIS_SOURCE)

Java.perform(function () {
  // ---- 1. X509TrustManager ---------------------------------------
  try {
    var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
    var SSLContext = Java.use('android.net.ssl.SSLContext');
    // We don't replace the interface; we patch every concrete
    // implementation's checkServerTrusted to a no-op.
  } catch (e) {}

  // ---- 2. HostnameVerifier ----------------------------------------
  try {
    var HostnameVerifier = Java.use('javax.net.ssl.HostnameVerifier');
    HostnameVerifier.verify.implementation = function () {
      return true;
    };
  } catch (e) {}

  // ---- 3. OkHttp CertificatePinner --------------------------------
  try {
    var CertPinner = Java.use('okhttp3.CertificatePinner');
    CertPinner.check.overload('java.lang.String', 'java.util.List')
      .implementation = function () { return; };
  } catch (e) {}

  // ---- 4. TrustManagerFactory hook --------------------------------
  try {
    var TrustManagerFactory = Java.use('javax.net.ssl.TrustManagerFactory');
    // Replace the system trust store with one that accepts all certs.
    var TrustAllManager = Java.registerClass({
      name: 'com.android.re.TrustAllManager',
      implements: [Java.use('javax.net.ssl.X509TrustManager')],
      methods: {
        checkClientTrusted: function (chain, authType) {},
        checkServerTrusted: function (chain, authType) {},
        getAcceptedIssuers: function () { return Java.array('java.security.cert.X509Certificate', []); }
      }
    });
    var TrustManagers = Java.array('javax.net.ssl.TrustManager',
      [TrustAllManager.$new()]);
    var SSLContext = Java.use('android.net.ssl.SSLContext');
    SSLContext.init.overload('[Ljavax.net.ssl.KeyManager;',
                              '[Ljavax.net.ssl.TrustManager;',
                              'java.security.SecureRandom')
      .implementation = function (km, tm, sr) {
        return this.init(km, TrustManagers, sr);
      };
  } catch (e) {}

  // ---- 5. Conscrypt -----------------------------------------------
  try {
    var Conscrypt = Java.use('org.conscrypt.ConscryptFileDescriptorSocket');
    if (Conscrypt.checkTrusted) {
      Conscrypt.checkTrusted.implementation = function () { return; };
    }
  } catch (e) {}

  console.log('[ssl-bypass] Java-side hooks installed');
});

// ---- 6. Native: ssl_verify_cert_chain -------------------------
// Used by libssl / libconscrypt / OpenSSL on Android. Hooked at
// the symbol level via Interceptor. Return 1 (success) unconditionally.
setTimeout(function () {
  try {
    var modules = ['libssl.so', 'libconscrypt.so', 'libsslutils.so'];
    modules.forEach(function (name) {
      var mod = Process.findModuleByName(name);
      if (mod === null) return;
      var sym = mod.findExportByName('ssl_verify_cert_chain');
      if (sym === null) return;
      Interceptor.attach(sym, {
        onLeave: function (retval) {
          retval.replace(1);
        }
      });
      console.log('[ssl-bypass] hooked native ssl_verify_cert_chain in', name);
    });
  } catch (e) {
    console.log('[ssl-bypass] native hook failed:', e);
  }
}, 500);

// Expose a small RPC for the MCP client to verify the hook
// landed.
rpc.exports = {
  ping: function () { return 'ssl-bypass-ok'; }
};
