/// Whether a path of this process's own (its bundle, its executable) is
/// inside a roothide bootstrap, and where that bootstrap's root is.
///
/// roothide names its root `.jbroot-` and sixteen hex digits under
/// `/var/containers/Bundle/Application`, and libroothide finds the root the
/// same way, off its own image path (`init.c`, `is_jbroot_name`). Nothing
/// else on the device says as much as reliably:
///
/// - The `.jbroot` link beside a binary is made by roothide's dpkg hook or
///   by the jailbreak when it loads one. A package installed another way has
///   none, and `dlopen` of `.jbroot/usr/lib/libroothide.dylib` then fails.
/// - roothide ships no `libroot.dylib`, and where one exists its prefix
///   spelling is not bootstrap identity.
/// - A fallback of "`/var/jb`, so rootless" turns either miss into a wrong
///   answer on a roothide device.
///
/// The daemon's `hello` stays the authority on the install root. This is for
/// what must be known before the daemon answers.
enum RoothideRoot {
    /// The path as far as its roothide root, or nil outside one. The path is
    /// read as spelled: resolving it could only lose the name looked for.
    static func containing(_ path: String) -> String? {
        let components = path.split(separator: "/")
        guard let index = components.firstIndex(where: isRootName) else { return nil }
        return "/" + components[...index].joined(separator: "/")
    }

    /// libroothide's `is_jbroot_name`: the last byte is the xor of the seven
    /// before it, so `.jbroot`, `.jbroot-test` and a mistyped name are not
    /// roots. Digits only: a sign is a number to `UInt64` and to `strtoull`,
    /// and no name roothide makes.
    private static func isRootName(_ name: Substring) -> Bool {
        let prefix = ".jbroot-"
        let digits = name.dropFirst(prefix.count)
        guard name.hasPrefix(prefix), digits.count == 16, digits.allSatisfy(\.isHexDigit),
              let value = UInt64(digits, radix: 16)
        else { return false }
        let check = (1 ... 7).reduce(UInt8(0)) { $0 ^ UInt8(truncatingIfNeeded: value >> ($1 * 8)) }
        return check == UInt8(truncatingIfNeeded: value)
    }
}
