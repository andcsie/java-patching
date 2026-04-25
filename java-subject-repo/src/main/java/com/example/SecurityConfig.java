package com.example;

import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.security.KeyManagementException;
import java.security.NoSuchAlgorithmException;
import java.security.cert.X509Certificate;

/**
 * Security configuration that may be affected by JDK security updates.
 *
 * Note: This code uses patterns that are affected by:
 * - TLS 1.0/1.1 deprecation in JDK 11.0.19+
 * - Certificate validation changes
 * - SSLSocket API changes
 */
public class SecurityConfig {

    /**
     * Creates an SSL context with specific protocols.
     * WARNING: TLS 1.0 and 1.1 are disabled by default in JDK 11.0.19+
     */
    public SSLContext createSSLContext() throws NoSuchAlgorithmException, KeyManagementException {
        SSLContext sslContext = SSLContext.getInstance("TLSv1.2");

        // This trust manager pattern may trigger security warnings
        TrustManager[] trustManagers = new TrustManager[]{
            new X509TrustManager() {
                @Override
                public void checkClientTrusted(X509Certificate[] chain, String authType) {
                    // Trust all - this is insecure!
                }

                @Override
                public void checkServerTrusted(X509Certificate[] chain, String authType) {
                    // Trust all - this is insecure!
                }

                @Override
                public X509Certificate[] getAcceptedIssuers() {
                    return new X509Certificate[0];
                }
            }
        };

        sslContext.init(null, trustManagers, null);
        return sslContext;
    }

    /**
     * Configure SSL socket with specific protocols.
     * Note: setEnabledProtocols behavior changed in security updates.
     */
    public void configureSocket(SSLSocket socket) {
        // This may fail if TLS 1.0/1.1 are disabled
        socket.setEnabledProtocols(new String[]{"TLSv1.2", "TLSv1.1", "TLSv1"});

        // Cipher suites may also be affected
        socket.setEnabledCipherSuites(new String[]{
            "TLS_RSA_WITH_AES_256_CBC_SHA256",
            "TLS_RSA_WITH_AES_128_CBC_SHA"
        });
    }

    /**
     * Create a socket factory.
     */
    public SSLSocketFactory getSocketFactory() throws Exception {
        return createSSLContext().getSocketFactory();
    }
}
