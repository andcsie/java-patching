package com.example;

import java.lang.reflect.Field;
import java.net.URL;
import java.net.URLClassLoader;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Base64;

/**
 * Main application demonstrating various JDK APIs
 * that may be affected by version upgrades.
 */
public class Application {

    public static void main(String[] args) throws Exception {
        System.out.println("Java Version: " + System.getProperty("java.version"));
        System.out.println("Starting application...");

        // Test various APIs
        testReflection();
        testClassLoading();
        testSecurityAPIs();
        testBase64();
    }

    /**
     * Reflection APIs - affected by module system restrictions.
     * In JDK 17+, --add-opens may be required.
     */
    private static void testReflection() throws Exception {
        // This pattern is affected by strong encapsulation
        Field field = String.class.getDeclaredField("value");
        field.setAccessible(true);  // May require --add-opens in JDK 17+

        System.out.println("Reflection test passed");
    }

    /**
     * ClassLoader APIs - URLClassLoader.close() behavior changed.
     */
    private static void testClassLoading() throws Exception {
        URL[] urls = new URL[]{new URL("file:///tmp/classes/")};
        URLClassLoader loader = new URLClassLoader(urls);

        try {
            // Load classes...
            System.out.println("ClassLoader test passed");
        } finally {
            loader.close();
        }
    }

    /**
     * Security APIs using AccessController.
     * AccessController is deprecated for removal in JDK 17+.
     */
    @SuppressWarnings("removal")
    private static void testSecurityAPIs() {
        String result = AccessController.doPrivileged(
            (PrivilegedAction<String>) () -> System.getProperty("user.home")
        );
        System.out.println("Home directory: " + result);
    }

    /**
     * Base64 encoding - no changes expected, just for completeness.
     */
    private static void testBase64() {
        String encoded = Base64.getEncoder().encodeToString("Hello, World!".getBytes());
        byte[] decoded = Base64.getDecoder().decode(encoded);
        System.out.println("Base64 test passed: " + new String(decoded));
    }
}
