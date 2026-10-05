import Foundation

func require(_ condition: Bool, _ line: Int = #line) {
    if !condition {
        print("failed at line \(line)")
        exit(1)
    }
}

let parent = "/var/containers/Bundle/Application"
// 0x01 ^ 0x23 ^ 0x45 ^ 0x67 ^ 0x89 ^ 0xAB ^ 0xCD == 0xEF
require(RoothideRoot.containing(parent + "/.jbroot-0123456789ABCDEF/Applications/Example.app")
    == parent + "/.jbroot-0123456789ABCDEF")
require(RoothideRoot.containing("/private" + parent + "/.jbroot-0123456789abcdef/usr/libexec/exampled")
    == "/private" + parent + "/.jbroot-0123456789abcdef")

for path in [
    "/var/jb/Applications/Example.app",
    "/private/preboot/hash/dopamine/procursus/Applications/Example.app",
    parent + "/.jbroot-0123456789ABCDEE/Applications/Example.app",
    parent + "/.jbroot-test/Applications/Example.app",
    parent + "/.jbroot-+123456789ABCDEF/Applications/Example.app",
    "/var/jb/Applications/Example.app/.jbroot/Applications/Example.app",
    "",
] {
    require(RoothideRoot.containing(path) == nil)
}
