import Foundation

let path = Bundle.main.executablePath!
let mode = CommandLine.arguments[1]
var calls = 0
var expected = false

func require(_ condition: Bool) {
    if !condition { exit(1) }
}

ExecutableWatch.start {
    require(expected)
    calls += 1
    require(calls == 1)
}

func mutate() {
    let backup = path + ".dpkg-tmp"
    let replacement = path + ".dpkg-new"
    switch mode {
    case "remove", "immediate-remove":
        expected = true
        require(unlink(path) == 0)
    case "replace":
        require(FileManager.default.createFile(atPath: replacement, contents: Data()))
        expected = true
        require(rename(replacement, path) == 0)
    case "dpkg", "rollback":
        require(link(path, backup) == 0)
        require(FileManager.default.createFile(atPath: replacement, contents: Data()))
        require(rename(replacement, path) == 0)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            require(calls == 0)
            if mode == "rollback" {
                require(rename(backup, path) == 0)
            } else {
                expected = true
                require(unlink(backup) == 0)
            }
        }
    case "unchanged": break
    default: exit(2)
    }
}

if mode == "immediate-remove" {
    // The main queue cannot deliver the registration handler yet.
    mutate()
} else {
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { mutate() }
}
DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
    require(calls == (expected ? 1 : 0))
    exit(0)
}
dispatchMain()
