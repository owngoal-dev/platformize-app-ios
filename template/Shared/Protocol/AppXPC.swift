#if canImport(XPC)
import CAppXPC
import XPC

/// The XPC constants, read through C rather than through Swift's XPC overlay.
///
/// Naming the SDK's XPC type, array-append or connection-error macros in Swift
/// links `/usr/lib/swift/libswiftXPC.dylib` as a required library, and iOS 15
/// does not have it: dyld terminates the process before `main` with "Library
/// not loaded". Through the C shim they are the libSystem globals they have
/// always been, the overlay stays weakly linked and unused, and the same binary
/// runs on iOS 15 and on iOS 26 — one path on every OS, so the version you test
/// on is the version that runs everywhere.
///
/// Put this file in whatever group every target already compiles (the app, the
/// daemon, the CLI), and let `make check` fail on any Swift file that spells
/// the macros directly.
public enum AppXPC {
    public static var typeArray: xpc_type_t { app_xpc_type_array() }
    public static var typeBool: xpc_type_t { app_xpc_type_bool() }
    public static var typeConnection: xpc_type_t { app_xpc_type_connection() }
    public static var typeData: xpc_type_t { app_xpc_type_data() }
    public static var typeDictionary: xpc_type_t { app_xpc_type_dictionary() }
    public static var typeError: xpc_type_t { app_xpc_type_error() }
    public static var typeInt64: xpc_type_t { app_xpc_type_int64() }
    public static var typeString: xpc_type_t { app_xpc_type_string() }
    public static var typeUInt64: xpc_type_t { app_xpc_type_uint64() }

    /// The index that appends rather than replaces, for `xpc_array_set_*`.
    public static var arrayAppend: Int { app_xpc_array_append() }

    public static var errorConnectionInterrupted: xpc_object_t { app_xpc_error_connection_interrupted() }
    public static var errorConnectionInvalid: xpc_object_t { app_xpc_error_connection_invalid() }
}
#endif
