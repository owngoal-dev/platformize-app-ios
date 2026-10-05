import Darwin
import Dispatch
import XPC

// Private or Mac-only in the iOS SDK headers, public in libSystem on every iOS
// this skill supports.

@_silgen_name("xpc_connection_create_mach_service")
func daemonCreateMachServiceListener(
    _ name: UnsafePointer<CChar>,
    _ queue: DispatchQueue?,
    _ flags: UInt64
) -> xpc_connection_t?

@_silgen_name("xpc_connection_get_audit_token")
func daemonConnectionAuditToken(_ connection: xpc_connection_t, _ token: UnsafeMutablePointer<audit_token_t>)

@_silgen_name("xpc_copy_entitlement_for_token")
func daemonCopyEntitlement(_ name: UnsafePointer<CChar>, _ token: UnsafeMutablePointer<audit_token_t>) -> xpc_object_t?

@_silgen_name("proc_pidpath")
func daemonProcPIDPath(_ pid: Int32, _ buffer: UnsafeMutableRawPointer, _ size: UInt32) -> Int32

/// `XPC_CONNECTION_MACH_SERVICE_LISTENER`.
let machServiceListener: UInt64 = 1

/// The canonical path of a running process's executable.
func executablePath(pid: Int32) -> String? {
    var buffer = [CChar](repeating: 0, count: Int(MAXPATHLEN))
    let length = buffer.withUnsafeMutableBytes { daemonProcPIDPath(pid, $0.baseAddress!, UInt32($0.count)) }
    return length > 0 ? canonicalPath(String(cString: buffer)) : nil
}

/// `realpath(3)`; nil for a path with an embedded NUL or one that does not resolve.
func canonicalPath(_ path: String) -> String? {
    guard !path.utf8.contains(0), let resolved = realpath(path, nil) else { return nil }
    defer { free(resolved) }
    return String(cString: resolved)
}
