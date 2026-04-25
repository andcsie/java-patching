package com.example;

import java.io.FilePermission;
import java.security.Permission;

/**
 * Legacy security manager usage.
 *
 * WARNING: SecurityManager is deprecated for removal in JDK 17+
 * This code demonstrates usage that will need migration.
 */
public class LegacySecurityManager extends SecurityManager {

    private final boolean strictMode;

    public LegacySecurityManager(boolean strictMode) {
        this.strictMode = strictMode;
    }

    @Override
    public void checkPermission(Permission perm) {
        if (strictMode) {
            // Strict checking
            super.checkPermission(perm);
        }
        // Otherwise allow
    }

    @Override
    public void checkRead(String file) {
        if (strictMode && file.contains("/etc/")) {
            throw new SecurityException("Cannot read system files: " + file);
        }
    }

    @Override
    public void checkWrite(String file) {
        if (strictMode) {
            super.checkWrite(file);
        }
    }

    @Override
    public void checkConnect(String host, int port) {
        // Log connection attempts
        System.out.println("Connection attempt to " + host + ":" + port);
    }

    @Override
    public void checkAccess(Thread t) {
        // Allow all thread access
    }

    /**
     * Install this security manager as the system security manager.
     */
    public static void install(boolean strictMode) {
        // This will fail in JDK 17+ with security manager disabled
        System.setSecurityManager(new LegacySecurityManager(strictMode));
    }

    /**
     * Check if security manager is active.
     */
    public static boolean isActive() {
        return System.getSecurityManager() != null;
    }
}
