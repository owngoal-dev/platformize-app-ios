import Darwin
import XPC

/// Decides before the first request is decoded: the audit token's euid (root
/// or mobile), the entitlements, then the executable on disk, which must be a
/// client this package installed and still root-owned and not writable by
/// anyone else. Require `platform-application` only while the app carries it.
struct PeerAuthenticator {
    private static let requiredEntitlements = [
        AppProtocol.clientEntitlement,
        "com.apple.private.security.no-sandbox",
        "platform-application",
    ]

    let installRoot: String

    func authenticate(_ connection: xpc_connection_t) -> Bool {
        var token = audit_token_t()
        daemonConnectionAuditToken(connection, &token)
        let euid = token.val.1
        let pid = Int32(bitPattern: token.val.5)
        guard pid > 1, euid == 0 || euid == 501,
              Self.requiredEntitlements.allSatisfy({ hasEntitlement($0, token: &token) }),
              let path = executablePath(pid: pid) else { return false }
        return AppProtocol.clientPaths.contains { client in
            canonicalPath(installRoot + client) == path && isRootOwnedExecutable(path)
        }
    }

    private func hasEntitlement(_ name: String, token: inout audit_token_t) -> Bool {
        guard let value = name.withCString({ daemonCopyEntitlement($0, &token) }) else { return false }
        return xpc_get_type(value) == AppXPC.typeBool && xpc_bool_get_value(value)
    }

    private func isRootOwnedExecutable(_ path: String) -> Bool {
        var metadata = stat()
        guard stat(path, &metadata) == 0 else { return false }
        return metadata.st_uid == 0
            && metadata.st_mode & S_IFMT == S_IFREG
            && metadata.st_mode & S_IXUSR != 0
            && metadata.st_mode & (S_IWGRP | S_IWOTH) == 0
    }
}
